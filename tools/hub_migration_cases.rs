// Behavior cases for extracted production migration functions.
// Windows junctions and Unix symlinks use real filesystem operations.
use super::*;
use octosense_app_contract::AppManifest;
use std::{fs, sync::atomic::{AtomicU64, Ordering}};

struct Fixture { root: PathBuf, apps: PathBuf, bundle: PathBuf }
impl Fixture {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let root = std::env::temp_dir().join(format!("hub-contract-migration-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        fs::create_dir(&root).unwrap();
        let bundle = root.join("fixture");
        fs::create_dir(&bundle).unwrap();
        // Exact executable, icon, screenshot and listing payloads from the Hub's
        // common Fixture::new. Migration checks identity/digest, not signatures.
        fs::write(bundle.join("main.splash"), "Label{text: \"Example\"}").unwrap();
        fs::write(bundle.join("icon.svg"), r##"<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" fill="#146"/></svg>"##).unwrap();
        use base64::Engine;
        fs::write(bundle.join("screen.png"), base64::engine::general_purpose::STANDARD.decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=").unwrap()).unwrap();
        fs::write(bundle.join("listing.json"), serde_json::to_vec(&serde_json::json!({
            "schema": 1, "description": "Publisher regression fixture", "category": "utilities",
            "screenshots": ["screen.png"], "icon": "icon.svg", "platforms": ["android"],
            "publisher": {"name": "Example", "support": "https://example.test/support", "privacy_policy_url": "https://example.test/privacy"},
            "age_rating": "all"
        })).unwrap()).unwrap();
        let mut manifest = AppManifest::parse(r#"{"schema":1,"id":"example-app","version":"1.0.0","name":"Example","integrity":{"bundle_blake3":""}}"#).unwrap();
        manifest.integrity.bundle_blake3 = digest_dir(&bundle).unwrap();
        fs::write(bundle.join("manifest.json"), serde_json::to_vec_pretty(&manifest).unwrap()).unwrap();
        let apps = root.join("apps");
        fs::create_dir(&apps).unwrap();
        Self { root, apps, bundle }
    }
    fn old(&self, name: &str) -> PathBuf { self.apps.join("example-app").join(name) }
    fn modern(&self) { copy_dir(&self.bundle, &installed_bundle_dir(&self.apps, "example-app")); }
    fn valid_old(&self, name: &str) { copy_dir(&self.bundle, &self.old(name)); }
    fn data(&self, name: &str) {
        fs::create_dir_all(self.old(name)).unwrap();
        fs::write(self.old(name).join("notes.txt"), "user data").unwrap();
    }
    fn data_stays(&self, name: &str) { assert_eq!(fs::read_to_string(self.old(name).join("notes.txt")).unwrap(), "user data"); }
    fn installed_matches(&self) {
        let actual = installed_bundle_dir(&self.apps, "example-app");
        assert_eq!(digest_dir(&actual).unwrap(), digest_dir(&self.bundle).unwrap());
        assert_eq!(fs::read(actual.join("manifest.json")).unwrap(), fs::read(self.bundle.join("manifest.json")).unwrap());
    }
}
impl Drop for Fixture { fn drop(&mut self) { let _ = fs::remove_dir_all(&self.root); } }
fn copy_dir(from: &Path, to: &Path) {
    fs::create_dir_all(to).unwrap();
    for entry in fs::read_dir(from).unwrap() {
        let entry = entry.unwrap();
        let target = to.join(entry.file_name());
        if entry.file_type().unwrap().is_dir() { copy_dir(&entry.path(), &target); }
        else { fs::copy(entry.path(), target).unwrap(); }
    }
}

#[test]
fn valid_legacy_moves_once_and_preserves_data() {
    let f = Fixture::new(); f.valid_old("bundle"); f.data("data");
    adopt_legacy_installs(&f.apps).unwrap();
    assert!(!f.old("bundle").exists()); f.installed_matches(); f.data_stays("data");
    adopt_legacy_installs(&f.apps).unwrap(); f.installed_matches(); f.data_stays("data");
}
#[test]
fn current_install_preserves_data_named_bundle() {
    let f = Fixture::new(); f.modern(); f.data("bundle");
    adopt_legacy_installs(&f.apps).unwrap(); f.installed_matches(); f.data_stays("bundle");
}
#[test]
fn current_install_preserves_update_name_data() {
    let f = Fixture::new(); f.modern(); f.data(".bundle-previous"); f.data(".bundle-next");
    adopt_legacy_installs(&f.apps).unwrap();
    f.installed_matches(); f.data_stays(".bundle-previous"); f.data_stays(".bundle-next");
}
#[test]
fn incomplete_modern_install_preserves_all_legacy_paths() {
    let f = Fixture::new();
    copy_dir(&f.bundle, &install_root(&f.apps, "example-app").join(".bundle-previous"));
    for name in ["bundle", ".bundle-previous", ".bundle-next"] { f.valid_old(name); }
    adopt_legacy_install(&f.apps, "example-app").unwrap();
    assert!(!installed_bundle_dir(&f.apps, "example-app").exists());
    for name in ["bundle", ".bundle-previous", ".bundle-next"] { assert!(f.old(name).join("manifest.json").is_file()); }
}
#[test]
fn empty_modern_root_retries_the_verified_legacy_move() {
    let f = Fixture::new(); f.valid_old("bundle");
    fs::create_dir_all(install_root(&f.apps, "example-app")).unwrap();
    adopt_legacy_install(&f.apps, "example-app").unwrap();
    f.installed_matches(); assert!(!f.old("bundle").exists());
}
#[test]
fn unknown_data_directories_with_invalid_manifests_stay() {
    let f = Fixture::new();
    for name in ["bundle", ".bundle-previous", ".bundle-next"] { f.data(name); fs::write(f.old(name).join("manifest.json"), "{}").unwrap(); }
    adopt_legacy_installs(&f.apps).unwrap(); adopt_legacy_installs(&f.apps).unwrap();
    assert!(!install_root(&f.apps, "example-app").exists());
    for name in ["bundle", ".bundle-previous", ".bundle-next"] { f.data_stays(name); }
}
#[test]
fn unknown_data_files_stay() {
    let f = Fixture::new(); fs::create_dir_all(f.apps.join("example-app")).unwrap();
    for name in ["bundle", ".bundle-previous", ".bundle-next"] { fs::write(f.old(name), "user data").unwrap(); }
    adopt_legacy_install(&f.apps, "example-app").unwrap();
    assert!(!install_root(&f.apps, "example-app").exists());
    for name in ["bundle", ".bundle-previous", ".bundle-next"] { assert_eq!(fs::read_to_string(f.old(name)).unwrap(), "user data"); }
}
#[test]
fn manifest_id_mismatch_is_not_migrated() {
    let f = Fixture::new(); let legacy = f.apps.join("another-app/bundle"); copy_dir(&f.bundle, &legacy);
    adopt_legacy_installs(&f.apps).unwrap();
    assert!(legacy.join("manifest.json").is_file()); assert!(!install_root(&f.apps, "another-app").exists());
}
#[test]
fn digest_mismatch_is_not_migrated() {
    let f = Fixture::new(); f.valid_old("bundle"); fs::write(f.old("bundle").join("notes.txt"), "changed after install").unwrap();
    adopt_legacy_installs(&f.apps).unwrap();
    assert_eq!(fs::read_to_string(f.old("bundle").join("notes.txt")).unwrap(), "changed after install");
    assert!(!install_root(&f.apps, "example-app").exists());
}
#[test]
fn valid_previous_recovers_without_bundle_and_preserves_next() {
    let f = Fixture::new(); f.valid_old(".bundle-previous"); f.data(".bundle-next");
    adopt_legacy_install(&f.apps, "example-app").unwrap();
    f.installed_matches(); assert!(!f.old(".bundle-previous").exists()); f.data_stays(".bundle-next");
}
#[test]
fn valid_previous_recovers_beside_unknown_bundle() {
    let f = Fixture::new(); f.valid_old(".bundle-previous"); f.data("bundle");
    adopt_legacy_install(&f.apps, "example-app").unwrap();
    f.installed_matches(); assert!(!f.old(".bundle-previous").exists()); f.data_stays("bundle");
}
#[test]
fn valid_bundle_preserves_unknown_update_data() {
    let f = Fixture::new(); f.valid_old("bundle"); f.data(".bundle-previous"); f.data(".bundle-next");
    adopt_legacy_install(&f.apps, "example-app").unwrap();
    f.installed_matches(); f.data_stays(".bundle-previous"); f.data_stays(".bundle-next");
}
#[test]
fn next_only_valid_bundle_is_not_published() {
    let f = Fixture::new(); f.valid_old(".bundle-next");
    adopt_legacy_install(&f.apps, "example-app").unwrap();
    assert!(f.old(".bundle-next").join("manifest.json").is_file()); assert!(!install_root(&f.apps, "example-app").exists());
}
#[test]
fn completed_legacy_updates_keep_the_published_bundle() {
    let f = Fixture::new(); for name in ["bundle", ".bundle-previous", ".bundle-next"] { f.valid_old(name); }
    adopt_legacy_install(&f.apps, "example-app").unwrap(); f.installed_matches();
    assert!(!f.old("bundle").exists());
    for name in [".bundle-previous", ".bundle-next"] { assert!(f.old(name).join("manifest.json").is_file()); }
}
#[cfg(any(unix, windows))]
fn link_directory(from: &Path, to: &Path) {
    #[cfg(unix)] std::os::unix::fs::symlink(from, to).unwrap();
    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        let result = std::process::Command::new("cmd.exe").args(["/C", "mklink", "/J"]).arg(to).arg(from).creation_flags(0x08000000).output().unwrap();
        assert!(result.status.success(), "{}", String::from_utf8_lossy(&result.stderr));
    }
}
#[cfg(any(unix, windows))]
#[test]
fn linked_app_directory_is_not_followed() {
    let f = Fixture::new(); let outside = f.root.join("outside"); copy_dir(&f.bundle, &outside.join("bundle"));
    link_directory(&outside, &f.apps.join("example-app"));
    adopt_legacy_install(&f.apps, "example-app").unwrap(); adopt_legacy_installs(&f.apps).unwrap();
    assert!(outside.join("bundle/manifest.json").is_file()); assert!(!install_root(&f.apps, "example-app").exists());
}
#[cfg(any(unix, windows))]
#[test]
fn linked_installs_directory_is_not_followed() {
    let f = Fixture::new(); let outside = f.root.join("outside"); fs::create_dir(&outside).unwrap(); f.valid_old("bundle");
    link_directory(&outside, &f.apps.join(INSTALLS_DIR));
    adopt_legacy_install(&f.apps, "example-app").unwrap();
    assert!(f.old("bundle").join("manifest.json").is_file()); assert!(!outside.join("example-app").exists());
}
#[cfg(any(unix, windows))]
#[test]
fn linked_legacy_bundle_paths_are_preserved() {
    let f = Fixture::new(); fs::create_dir_all(f.apps.join("example-app")).unwrap();
    for name in ["bundle", ".bundle-previous", ".bundle-next"] { link_directory(&f.bundle, &f.old(name)); }
    adopt_legacy_install(&f.apps, "example-app").unwrap();
    assert!(!install_root(&f.apps, "example-app").exists());
    for name in ["bundle", ".bundle-previous", ".bundle-next"] { assert!(fs::symlink_metadata(f.old(name)).is_ok()); }
    assert!(f.bundle.join("manifest.json").is_file());
}
