// IPC communication standard interface

import { IPCRequest, IPCResponse } from '../ipc/ipc-types';

export interface IpcAdapter {
    send(message: IPCRequest): void;
    onReceive(callback: (msg: IPCResponse) => void): void;
}
