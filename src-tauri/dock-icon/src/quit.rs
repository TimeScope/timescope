use objc2::{
    ffi,
    runtime::{AnyObject, Imp, Sel},
    sel, MainThreadMarker,
};
use objc2_app_kit::{NSApplication, NSApplicationTerminateReply};
use std::sync::OnceLock;

static QUIT_GUARD: OnceLock<Box<dyn Fn() -> bool + Send + Sync>> = OnceLock::new();

extern "C-unwind" fn should_terminate(
    _: &AnyObject,
    _: Sel,
    _: &NSApplication,
) -> NSApplicationTerminateReply {
    if QUIT_GUARD.get().is_some_and(|guard| guard()) {
        NSApplicationTerminateReply::TerminateCancel
    } else {
        NSApplicationTerminateReply::TerminateNow
    }
}

/// Give AppKit's Quit request to the caller. Returning true defers shutdown
/// to the app's own close flow, which can later request an approved exit.
pub fn install_quit_guard(
    guard: impl Fn() -> bool + Send + Sync + 'static,
) -> Result<(), &'static str> {
    let main = MainThreadMarker::new().ok_or("Quit guard requires the main thread")?;
    let app = NSApplication::sharedApplication(main);
    let delegate = app.delegate().ok_or("AppKit delegate unavailable")?;
    let delegate_object: &AnyObject = (*delegate).as_ref();
    let class = delegate_object.class();
    let selector = sel!(applicationShouldTerminate:);
    if class.instance_method(selector).is_some() {
        return Err("AppKit delegate already handles termination");
    }
    QUIT_GUARD
        .set(Box::new(guard))
        .map_err(|_| "Quit guard already installed")?;
    // SAFETY: Add a previously absent NSObject delegate method, on the main
    // thread, to the app's existing delegate. The callback matches AppKit's
    // object argument and NSUInteger return ABI on supported 64-bit Macs.
    let added = unsafe {
        type TerminateCallback =
            extern "C-unwind" fn(&AnyObject, Sel, &NSApplication) -> NSApplicationTerminateReply;
        let imp = std::mem::transmute::<TerminateCallback, Imp>(should_terminate);
        ffi::class_addMethod(
            std::ptr::from_ref(class).cast_mut(),
            selector,
            imp,
            c"Q@:@".as_ptr(),
        )
    };
    if !added.as_bool() {
        return Err("Could not install the AppKit Quit guard");
    }
    // Refresh AppKit's optional-method cache while retaining Tao's delegate.
    app.setDelegate(None);
    app.setDelegate(Some(&delegate));
    Ok(())
}
