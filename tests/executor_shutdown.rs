//! Regression stress for upstream async-executor #163/#164; not a sanitizer proof.
use async_executor::Executor;
use std::{
    future::Future,
    pin::Pin,
    sync::{Arc, Barrier, Mutex},
    task::{Context, Poll, Waker},
};

struct Park(Arc<Mutex<Option<Waker>>>);
impl Future for Park {
    type Output = ();
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
        *self.0.lock().unwrap() = Some(cx.waker().clone());
        Poll::Pending
    }
}

#[test]
fn external_wakers_remain_safe_during_and_after_executor_shutdown() {
    for i in 0..2000 {
        let slot = Arc::new(Mutex::new(None));
        let executor = Executor::new();
        executor.spawn(Park(slot.clone())).detach();
        assert!(executor.try_tick());
        let waker = slot.lock().unwrap().take().unwrap();
        if i % 2 == 0 {
            drop(executor);
            waker.wake();
        } else {
            let barrier = Arc::new(Barrier::new(2));
            let other = barrier.clone();
            let thread = std::thread::spawn(move || {
                other.wait();
                waker.wake();
            });
            barrier.wait();
            drop(executor);
            thread.join().unwrap();
        }
    }
}
