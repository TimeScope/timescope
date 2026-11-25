#[cfg(test)]
mod tests {
    use rstar::{PointDistance, RTree};

    fn points() -> Vec<[f64; 2]> {
        (0..4096)
            .map(|i| [((i * 73) % 4099) as f64, ((i * 127) % 4103) as f64])
            .collect()
    }

    #[test]
    fn ordered_queries_match_brute_force_across_large_trees() {
        let data = points();
        let tree = RTree::bulk_load(data.clone());
        for query in [[-200.0, 10.0], [2030.5, 997.25], [5000.0, 5000.0]] {
            let mut expected: Vec<_> = data.iter().map(|p| p.distance_2(&query)).collect();
            expected.sort_by(f64::total_cmp);
            let actual: Vec<_> = tree
                .nearest_neighbor_iter_with_distance_2(&query)
                .map(|(_, distance)| distance)
                .collect();
            assert_eq!(actual, expected);
            assert_eq!(
                tree.nearest_neighbor(&query).unwrap().distance_2(&query),
                expected[0]
            );
        }
    }

    #[test]
    fn ties_and_empty_trees_preserve_all_results() {
        let mut tree = RTree::<[f64; 2]>::new();
        assert!(tree.nearest_neighbor(&[0.0, 0.0]).is_none());
        assert_eq!(tree.nearest_neighbor_iter(&[0.0, 0.0]).count(), 0);
        for p in [[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0]] {
            tree.insert(p);
        }
        assert_eq!(tree.nearest_neighbors(&[0.0, 0.0]).len(), 4);
        assert!(tree
            .nearest_neighbor_iter(&[0.0, 0.0])
            .all(|p| p.distance_2(&[0.0, 0.0]) == 1.0));
    }

    #[test]
    fn removal_and_reinsertion_keep_nearest_and_range_queries_consistent() {
        let mut data = points();
        let mut tree = RTree::bulk_load(data.clone());
        for p in data.drain(..2048) {
            assert_eq!(tree.remove(&p), Some(p));
        }
        let inserted = [2048.5, 2048.5];
        tree.insert(inserted);
        assert_eq!(tree.nearest_neighbor(&inserted), Some(&inserted));
        data.push(inserted);
        let query = [2000.0, 2000.0];
        let count = data
            .iter()
            .filter(|p| p.distance_2(&query) <= 100_000.0)
            .count();
        assert_eq!(tree.locate_within_distance(query, 100_000.0).count(), count);
        assert_eq!(tree.size(), data.len());
    }
}
