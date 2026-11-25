use chronoscope::{engine::Engine, project::Project};
use serde_json::json;
#[test]
fn c17_clone_before_append_preserves_old_evidence_review_ticket_and_undo() {
    let dir = tempfile::tempdir().unwrap();
    let engine = Engine::new(
        Project::new(chronoscope::demo::dataset()),
        dir.path().join("app"),
    )
    .unwrap();
    engine.invoke("select", json!({"ids":["1"]})).unwrap();
    let before = engine.invoke("events", json!({"id":"1"})).unwrap()["events"][0].clone();
    let file = dir.path().join("append.csv");
    std::fs::write(
        &file,
        "entity,timestamp,label\nnew,bad,reject me\nnew,2026-01-01,new evidence\n",
    )
    .unwrap();
    let ticket = engine
        .invoke("import_preview", json!({"path":file}))
        .unwrap()["import_id"]
        .clone();
    engine.invoke("recovery_clear", json!({})).unwrap();
    let status = engine.invoke("workspace_status", json!({})).unwrap();
    assert_eq!(status["dirty"], false);
    let review = engine
        .invoke("import_commit", json!({"import_id":ticket,"append":true}))
        .unwrap();
    assert_eq!(review["needs_review"], true);
    assert_eq!(review["revision"], status["revision"]);
    assert_eq!(
        engine.invoke("workspace_status", json!({})).unwrap(),
        status
    );
    assert_eq!(
        engine.invoke("snapshot", json!({"compact":true})).unwrap()["count"],
        192
    );
    assert_eq!(
        engine.invoke("events", json!({"id":"1"})).unwrap()["events"][0],
        before
    );
    let applied = engine
        .invoke(
            "import_commit",
            json!({"import_id":ticket,"append":true,"accept_rejected":true}),
        )
        .unwrap();
    assert_eq!(applied["accepted"], 1);
    assert_eq!(
        engine.invoke("snapshot", json!({"compact":true})).unwrap()["count"],
        193
    );
    assert_eq!(
        engine.invoke("events", json!({"id":"194"})).unwrap()["events"][0]["label"],
        "new evidence"
    );
    assert_eq!(
        engine
            .invoke("selection_contains", json!({"ids":["1","194"]}))
            .unwrap()["selected"],
        json!([])
    );
    engine.invoke("undo", json!({})).unwrap();
    assert_eq!(
        engine
            .invoke("selection_contains", json!({"ids":["1"]}))
            .unwrap()["selected"],
        json!(["1"])
    );
    assert_eq!(
        engine.invoke("snapshot", json!({"compact":true})).unwrap()["count"],
        192
    );
    engine.invoke("redo", json!({})).unwrap();
    assert_eq!(
        engine.invoke("snapshot", json!({"compact":true})).unwrap()["count"],
        193
    );
    assert_eq!(
        engine.invoke("events", json!({"id":"1"})).unwrap()["events"][0],
        before
    );
}

#[test]
fn append_respects_the_saved_import_recipe_limit() {
    let dir = tempfile::tempdir().unwrap();
    let mut study = Project::empty();
    study.imports = vec![
        chronoscope::project::ImportRecipe {
            source: "previous.csv".into(),
            sheet: "CSV".into(),
            mapping: Default::default(),
        };
        1000
    ];
    let engine = Engine::new(study, dir.path().join("app")).unwrap();
    let file = dir.path().join("new.csv");
    std::fs::write(&file, "entity,timestamp\nnew,2026-01-01\n").unwrap();
    let ticket = engine
        .invoke("import_preview", json!({"path":file}))
        .unwrap()["import_id"]
        .clone();
    let error = engine
        .invoke("import_commit", json!({"import_id":ticket,"append":true}))
        .unwrap_err();
    assert!(error.contains("1000 import recipes"));
    let result = engine
        .invoke("import_commit", json!({"import_id":ticket,"append":false}))
        .unwrap();
    assert_eq!(result["accepted"], 1);
}
