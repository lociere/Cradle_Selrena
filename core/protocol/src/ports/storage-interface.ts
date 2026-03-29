// storage standard interface

export interface Storage {
    save(key: string, value: any): Promise<void>;
    load(key: string): Promise<any>;
}
