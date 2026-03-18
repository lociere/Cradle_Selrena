import { SceneRoutingRequest, SceneRoutingResult } from "@cradle-selrena/protocol";

export class SceneRoutingManager {
  private static _instance: SceneRoutingManager | null = null;

  public static get instance(): SceneRoutingManager {
    if (!SceneRoutingManager._instance) {
      SceneRoutingManager._instance = new SceneRoutingManager();
    }
    return SceneRoutingManager._instance;
  }

  private constructor() {}

  public resolve(request: SceneRoutingRequest): SceneRoutingResult {
    const vesselId = String(request.source?.vessel_id || "unknown").trim() || "unknown";
    const sourceType = request.source?.source_type || "unknown";
    const sourceId = String(request.source?.source_id || "default").trim() || "default";
    const actorId = String(request.routing?.actor?.actor_id || "").trim();
    const actorName = String(request.routing?.actor?.actor_name || "").trim();
    const requestedPolicy = request.routing?.session_policy || "by_source";
    const sessionPolicy = requestedPolicy === "by_actor" && actorId ? "by_actor" : "by_source";

    let sceneId = `${vesselId}:${sourceType}:${sourceId}`;
    if (sessionPolicy === "by_actor") {
      sceneId = `${sceneId}:actor:${actorId}`;
    }

    return {
      scene_id: sceneId,
      source: {
        vessel_id: vesselId,
        source_type: sourceType,
        source_id: sourceId,
      },
      source_type: sourceType,
      source_id: sourceId,
      actor_id: actorId || undefined,
      actor_name: actorName || undefined,
      session_policy: sessionPolicy,
    };
  }
}
