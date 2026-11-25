# Calamine 0.38.0 worksheet allocation limits

Source: the crates.io calamine 0.38.0 archive, SHA-256
`f431b67cba6122a1f7d26b7adafc71bbdf07026095fe811f5efc025d8748e1d8`.
TimeScope checks actual cell extents before building dense worksheet ranges.
The legacy XLS reader also caps the cumulative allocations for its eager
value and formula ranges and avoids reserving memory from declared dimensions.
Keep these checks until the dependency exposes equivalent bounded reading.
