// domain events base class

export type EventType = string;

export abstract class DomainEvent {
  readonly occurredAt: number;

  constructor(occurredAt?: number) {
    this.occurredAt = occurredAt ?? Date.now();
  }
}
