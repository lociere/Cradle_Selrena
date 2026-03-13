// perception event definitions

import { DomainEvent } from './domain-events';

export class PerceptionEvent extends DomainEvent {
    constructor(public payload: any) {
        super();
    }
}
