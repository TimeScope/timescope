use chronoscope::{demos, engine::Engine, project::Project};
use serde_json::json;

#[test]
fn ancient_y_keeps_source_evidence_without_lineage_specific_views() {
    let dir = tempfile::tempdir().unwrap();
    let project = demos::load("ancient-y-dna", dir.path()).unwrap();
    project.validate().unwrap();
    assert_eq!(project.dataset.events.len(), 1708);
    assert_eq!(project.provenance[0].license, "CC BY 4.0");
    assert_eq!(project.provenance[1].license, "CC0 1.0");
    assert_eq!(project.views.len(), 11);
    assert!(project.views.iter().all(|view| !view.name.contains("I1a")));
    let collegno = project
        .dataset
        .events
        .iter()
        .find(|event| event.attrs["specimen"] == "CL63")
        .unwrap();
    assert_eq!(collegno.attrs["y_haplogroup_reported"], "I1a3");
    assert_eq!(collegno.attrs["y_assignment_selected"], "I1");
    assert!(project.dataset.events.iter().all(|event| {
        !event.attrs["y_haplogroup_reported"].is_empty()
            && event.attrs.contains_key("Age (BC)")
            && event.end.is_none()
    }));
    assert!(project.views.iter().all(|view| {
        let display = view.scene.display.as_ref().unwrap();
        !display.show_tracks && !display.show_trails
    }));
}

#[test]
fn ancient_y_catalog_regional_views_and_metadata_survive_reopen() {
    let dir = tempfile::tempdir().unwrap();
    let engine = Engine::new(Project::empty(), dir.path().into()).unwrap();
    engine
        .invoke("demo_open", json!({"id":"ancient-y-dna"}))
        .unwrap();
    let initial = engine.invoke("snapshot", json!({"compact":true})).unwrap();
    assert_eq!(initial["count"], 1708);
    assert_eq!(initial["visible"], 1371);
    assert_eq!(initial["scene"]["mode"], "globe");
    for (index, expected) in [(1, 964), (2, 219), (3, 176), (4, 150), (9, 1031)] {
        engine
            .invoke("restore_view", json!({"index":index}))
            .unwrap();
        let snapshot = engine.invoke("snapshot", json!({"compact":true})).unwrap();
        assert_eq!(snapshot["visible"], expected, "saved view {index}");
    }
    engine.invoke("restore_view", json!({"index":9})).unwrap();
    let path = dir.path().join("ancient-y-copy.chronoscope");
    engine.invoke("save", json!({"path":path})).unwrap();
    engine.invoke("open", json!({"path":path})).unwrap();
    let after = engine.invoke("snapshot", json!({"compact":true})).unwrap();
    assert_eq!(after["count"], 1708);
    assert_eq!(after["visible"], 1031);
    let records = engine.invoke("events", json!({"limit":20})).unwrap();
    assert_eq!(records["events"].as_array().unwrap().len(), 20);
    assert!(records["events"]
        .as_array()
        .unwrap()
        .iter()
        .all(|event| { event["attrs"]["y_assignment_tree"] == "AADR v66.p1 / ISOGG v15.73" }));
    assert!(engine.invoke("workspace_status", json!({})).unwrap()["source"].is_string());
}
