// action event definitions

import { DomainEvent } from './domain-events';

export class ActionEvent extends DomainEvent {
    constructor(public actionType: string, public data: any) {
        super();
    }
}
