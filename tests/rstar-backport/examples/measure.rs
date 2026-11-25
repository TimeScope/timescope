use rstar::RTree;
use std::{hint::black_box, time::Instant};

fn main() {
    let points: Vec<_> = (0..100_000)
        .map(|i| [((i * 73) % 100_003) as f64, ((i * 127) % 100_019) as f64])
        .collect();
    let tree = RTree::bulk_load(points);
    let queries: Vec<_> = (0..10_000)
        .map(|i| {
            [
                ((i * 37) % 100_003) as f64 + 0.25,
                ((i * 61) % 100_019) as f64 + 0.5,
            ]
        })
        .collect();
    for _ in 0..2 {
        for query in &queries {
            black_box(tree.nearest_neighbor(black_box(query)));
        }
    }
    let mut samples = Vec::new();
    let mut checksum = 0.0;
    for _ in 0..7 {
        let start = Instant::now();
        for query in &queries {
            let point = tree.nearest_neighbor(black_box(query)).unwrap();
            checksum += black_box(point[0] + point[1]);
        }
        samples.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    samples.sort_by(f64::total_cmp);
    println!("{{\"records\":100000,\"queries_per_sample\":10000,\"median_ms\":{},\"samples_ms\":{:?},\"checksum\":{}}}", samples[3], samples, checksum);
}
