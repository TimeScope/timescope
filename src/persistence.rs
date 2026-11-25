//! Private staged file replacement. Cancellation has a single pre-rename
//! boundary; after replacement we finish durability work and disclose commit.
use std::{
    path::Path,
    time::{Duration, Instant},
};
pub(crate) fn persist_workspace(file: tempfile::NamedTempFile, path: &Path) -> Result<(), String> {
    crate::input_limits::ensure_workspace(file.path())?;
    persist(file, path)
}

pub(crate) fn persist(file: tempfile::NamedTempFile, path: &Path) -> Result<(), String> {
    file.as_file().sync_all().map_err(|e| e.to_string())?;
    crate::operation::progress(0, Some(1), "Committing external file");
    crate::operation::check()?;
    #[cfg(unix)]
    let parent = std::fs::File::open(
        path.parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new(".")),
    )
    .ok();
    file.persist(path).map_err(|e| e.to_string())?;
    crate::operation::file_committed();
    #[cfg(unix)]
    if parent.is_none_or(|directory| directory.sync_all().is_err()) {
        // The rename already committed: never misreport it as an aborted save.
        eprintln!("TimeScope: output saved; parent directory sync unavailable");
    }
    Ok(())
}
pub(crate) fn backup(
    source: &rusqlite::Connection,
    target: &mut rusqlite::Connection,
) -> Result<(), String> {
    use rusqlite::backup::{Backup, StepResult};
    let backup = Backup::new(source, target).map_err(|e| e.to_string())?;
    let mut busy_since = None;
    loop {
        crate::operation::check()?;
        let state = backup.step(1024).map_err(|e| e.to_string())?;
        let progress = backup.progress();
        crate::operation::progress(
            (progress.pagecount - progress.remaining).max(0) as u64,
            Some(progress.pagecount.max(0) as u64),
            "Staging database pages",
        );
        match state {
            StepResult::Done => return Ok(()),
            StepResult::More => busy_since = None,
            StepResult::Busy | StepResult::Locked => {
                if busy_since.get_or_insert_with(Instant::now).elapsed() > Duration::from_secs(30) {
                    return Err("UNAVAILABLE: database backup remained busy".into());
                }
                std::thread::sleep(Duration::from_millis(25));
            }
            _ => return Err("Database backup returned an unsupported state".into()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn oversized_workspace_keeps_the_existing_save() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("study.timescope");
        std::fs::write(&path, b"previous workspace").unwrap();
        let staged = tempfile::NamedTempFile::new_in(dir.path()).unwrap();
        staged
            .as_file()
            .set_len(crate::input_limits::MAX_INPUT + 1)
            .unwrap();
        assert!(persist_workspace(staged, &path).is_err());
        assert_eq!(std::fs::read(&path).unwrap(), b"previous workspace");
    }
}
