// multimodal related types

export type ModalityType = "text" | "image" | "video";

export interface ModelInputItem {
    modality: ModalityType;
    text?: string;
    uri?: string;
    mime_type?: string;
    description_hint?: string;
    metadata?: Record<string, unknown>;
}

export interface ModelInput {
    items: ModelInputItem[];
}
