// domain events base class

export abstract class DomainEvent {
    readonly occurredAt: number = Date.now();
}
