use std::path::{Path, PathBuf};
pub const INSTALLS_DIR: &str = ".bundles";

/// An app's installation: `bundle/`, and the staging an update uses.
pub fn install_root(app_data_root: &Path, app_id: &str) -> PathBuf {
    app_data_root.join(INSTALLS_DIR).join(app_id)
}

/// The installed bundle the store verifies and launches from.
pub fn installed_bundle_dir(app_data_root: &Path, app_id: &str) -> PathBuf {
    install_root(app_data_root, app_id).join("bundle")
}

/// Move every install made before [`INSTALLS_DIR`] out of its app's
/// storage. Idempotent and cheap when there is nothing to move.
pub fn adopt_legacy_installs(app_data_root: &Path) -> Result<(), String> {
    let entries = match std::fs::read_dir(app_data_root) {
        Ok(entries) => entries,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(()),
        Err(e) => return Err(format!("cannot read {}: {e}", app_data_root.display())),
    };
    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        let name = entry.file_name();
        let Some(id) = name.to_str() else { continue };
        if id.starts_with('.') || !entry.file_type().map_err(|e| e.to_string())?.is_dir() {
            continue;
        }
        adopt_legacy_install(app_data_root, id)?;
    }
    Ok(())
}

/// Move one app's install from its storage (`<root>/<id>/bundle`, the
/// layout before [`INSTALLS_DIR`]) to [`installed_bundle_dir`]. An update
/// interrupted in the old layout is settled first, as the store's recovery
/// would; an install already in the new place wins over a stale old copy.
/// Nothing found is followed through a symlink.
pub fn adopt_legacy_install(app_data_root: &Path, app_id: &str) -> Result<(), String> {
    let legacy = app_data_root.join(app_id);
    let (bundle, previous, next) = (legacy.join("bundle"), legacy.join(".bundle-previous"), legacy.join(".bundle-next"));
    let is_dir = |path: &Path| std::fs::symlink_metadata(path).is_ok_and(|m| m.is_dir());
    let remove = |path: &Path| match std::fs::symlink_metadata(path) {
        Ok(m) if m.is_dir() => std::fs::remove_dir_all(path),
        Ok(_) => std::fs::remove_file(path),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(e),
    };
    let fail = |what: &str, e: std::io::Error| format!("cannot move {app_id}'s install out of its storage ({what}): {e}");
    remove(&next).map_err(|e| fail("an interrupted download", e))?;
    if is_dir(&previous) && !is_dir(&bundle) {
        remove(&bundle).map_err(|e| fail("a stray entry", e))?;
        std::fs::rename(&previous, &bundle).map_err(|e| fail("the last complete bundle", e))?;
    } else {
        remove(&previous).map_err(|e| fail("a previous bundle", e))?;
    }
    if !is_dir(&bundle) {
        return remove(&bundle).map_err(|e| fail("a stray entry", e));
    }
    let target = installed_bundle_dir(app_data_root, app_id);
    if std::fs::symlink_metadata(&target).is_ok() {
        return remove(&bundle).map_err(|e| fail("a stale copy", e));
    }
    std::fs::create_dir_all(install_root(app_data_root, app_id)).map_err(|e| fail("its new place", e))?;
    std::fs::rename(&bundle, &target).map_err(|e| fail("the bundle", e))
}


#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    fn root(name: &str, modern: bool) -> PathBuf {
        let p = std::env::temp_dir().join(format!("hub-baseline-{}-{name}", std::process::id()));
        if p.exists() { fs::remove_dir_all(&p).unwrap(); }
        fs::create_dir_all(p.join("example-app")).unwrap();
        if modern {
            fs::create_dir_all(p.join(".bundles/example-app/bundle")).unwrap();
            fs::write(p.join(".bundles/example-app/bundle/manifest.json"), "{}").unwrap();
        }
        p
    }
    fn add_data(p: &Path, directory: &str) {
        fs::create_dir_all(p.join("example-app").join(directory)).unwrap();
        fs::write(p.join("example-app").join(directory).join("notes.txt"), "user data").unwrap();
    }
    fn assert_data(p: &Path, directory: &str) {
        assert_eq!(fs::read_to_string(p.join("example-app").join(directory).join("notes.txt")).unwrap(), "user data");
    }
    #[test]
    fn migration_preserves_app_data_named_bundle_when_a_new_install_exists() {
        let p = root("current-bundle", true);
        add_data(&p, "bundle");
        adopt_legacy_installs(&p).unwrap();
        assert_data(&p, "bundle");
        fs::remove_dir_all(p).unwrap();
    }
}
