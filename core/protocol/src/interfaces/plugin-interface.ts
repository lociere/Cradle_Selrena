// plugin standard interface

export interface Plugin {
    initialize(): Promise<void>;
    shutdown(): Promise<void>;
}
