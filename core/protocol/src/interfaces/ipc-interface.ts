// IPC communication standard interface

export interface IpcAdapter {
    send(message: any): void;
    onReceive(callback: (msg: any) => void): void;
}
