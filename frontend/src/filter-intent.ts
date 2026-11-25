interface Intent<T> {
  workspace: string | undefined;
  delta: Partial<T>;
}

/** Serial latest-intent writes. Each update rebases only its changed fields on
 * current engine state; CAS prevents overwriting an intervening external write. */
export class FilterIntent<T extends object> {
  private pending: Intent<T> | null = null;
  private applying: Intent<T> | null = null;
  private work: Promise<void> | null = null;
  private resolve: (() => void) | null = null;
  private reject: ((e: unknown) => void) | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private draining = false;
  private progressive = false;
  private failure: unknown;
  private refreshPending = false;
  constructor(
    private read: () => Promise<{ filter: T; revision: number; workspace?: string }>,
    private write: (filter: T, revision: number, workspace?: string) => Promise<unknown>,
    private applied: () => Promise<void>,
    private workspace: () => string | undefined = () => undefined,
  ) {}
  private current(intent: Intent<T> | null) {
    return intent?.workspace === this.workspace() ? intent?.delta : undefined;
  }
  desired(base: T): T {
    return { ...base, ...this.current(this.applying), ...this.current(this.pending) };
  }
  protects(key: keyof T): boolean {
    return (
      !!this.work &&
      (key in (this.current(this.pending) || {}) || key in (this.current(this.applying) || {}))
    );
  }
  enqueue(delta: Partial<T>, delay = 0, progressive = false): Promise<void> {
    this.progressive ||= progressive;
    this.pending = {
      workspace: this.workspace(),
      delta: { ...this.current(this.pending), ...delta },
    };
    this.prepare();
    clearTimeout(this.timer);
    if (delay) this.timer = setTimeout(() => this.start(), delay);
    else this.start();
    return this.work!;
  }
  idle(): Promise<void> {
    return (
      this.work ||
      (this.failure ? Promise.reject(this.failure) : Promise.resolve())
    );
  }
  flush(): Promise<void> {
    clearTimeout(this.timer);
    if (this.pending || this.refreshPending) this.prepare();
    this.start();
    return this.idle();
  }
  private prepare() {
    if (this.work) return;
    this.failure = undefined;
    this.work = new Promise<void>((resolve, reject) => {
      this.resolve = resolve;
      this.reject = reject;
    });
  }
  private start() {
    if (this.draining || !this.work) return;
    this.draining = true;
    void this.drain();
  }
  private async drain() {
    try {
      while (this.pending || this.refreshPending) {
        if (!this.pending) {
          await this.applied();
          this.refreshPending = false;
          continue;
        }
        const intent = this.pending;
        this.pending = null;
        this.applying = intent;
        try {
          for (let attempt = 0; ; attempt++) {
            const state = await this.read();
            if (intent.workspace !== state.workspace) break;
            try {
              await this.write(
                { ...state.filter, ...intent.delta },
                state.revision,
                intent.workspace,
              );
              break;
            } catch (e) {
              if (attempt >= 2 || !(e as Error).message?.includes("CONFLICT:"))
                throw e;
            }
          }
        } catch (e) {
          const pending = this.pending as Intent<T> | null;
          if (!pending || pending.workspace === intent.workspace)
            this.pending = { ...intent, delta: { ...intent.delta, ...pending?.delta } };
          throw e;
        }
        this.applying = null;
        this.refreshPending = true;
        // Scrubbing must publish intermediate frames even while newer input arrives.
        // The next write still coalesces all pending deltas into one latest intent.
        if (this.pending && this.progressive) {
          await this.applied();
          this.refreshPending = false;
        }
      }
      this.resolve?.();
    } catch (e) {
      this.failure = e;
      this.reject?.(e);
    } finally {
      this.applying = null;
      this.draining = false;
      this.progressive = false;
      this.work = null;
      this.resolve = null;
      this.reject = null;
    }
  }
}
