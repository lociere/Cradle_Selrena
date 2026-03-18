import path from "path";
import { promises as fs } from "fs";
import { PluginSceneTranscriptEntry } from "@cradle-selrena/protocol";
import { getLogger } from "../../core/observability/logger";
import { resolveRepoRoot } from "../../core/utils/path-utils";

const logger = getLogger("plugin-scene-transcript");

export class PluginSceneTranscriptService {
  private static _instance: PluginSceneTranscriptService | null = null;

  public static get instance(): PluginSceneTranscriptService {
    if (!PluginSceneTranscriptService._instance) {
      PluginSceneTranscriptService._instance = new PluginSceneTranscriptService();
    }
    return PluginSceneTranscriptService._instance;
  }

  private constructor() {}

  public async append(pluginId: string, entry: PluginSceneTranscriptEntry): Promise<void> {
    const content = this.normalizeContent(entry.content);
    if (!content) {
      return;
    }

    const target = this.resolveTarget(entry);
    await fs.mkdir(path.dirname(target.filePath), { recursive: true });
    await this.ensureHeader(target.filePath, target);

    const line = this.formatEntry(entry, content);
    await fs.appendFile(target.filePath, `${line}\n`, "utf8");
    await this.trimFile(target.filePath, 80);

    logger.debug("插件场景转录已追加", {
      plugin_id: pluginId,
      file_path: target.filePath,
      scene_scope: entry.scene_scope,
      transcript_scene_id: entry.transcript_scene_id,
    });
  }

  private resolveTarget(entry: PluginSceneTranscriptEntry): {
    filePath: string;
    scope: string;
    sceneLabel: string;
    ownerLabel: string;
    summary: string;
  } {
    const repoRoot = resolveRepoRoot();
    const rootDir = entry.root_dir && entry.root_dir.trim()
      ? (path.isAbsolute(entry.root_dir) ? entry.root_dir : path.resolve(repoRoot, entry.root_dir))
      : path.resolve(repoRoot, "data", "memory", "plugin-transcripts");

    if (entry.scene_scope === "group_scene") {
      return {
        filePath: path.join(rootDir, "scenes", "group", `${String(entry.transcript_scene_id || "unknown")}.md`),
        scope: "group_scene",
        sceneLabel: `group:${entry.transcript_scene_id}`,
        ownerLabel: entry.owner_label || `group:${entry.transcript_scene_id}`,
        summary: entry.summary || "该文件记录一个群场景内的连续对话转录。",
      };
    }

    if (entry.scene_scope === "private_session") {
      const identityScope = String(entry.identity_scope || "external_users");
      const ownerId = String(entry.owner_id || entry.transcript_scene_id || "unknown");
      return {
        filePath: path.join(rootDir, "users", identityScope, "private", `${ownerId}.md`),
        scope: identityScope,
        sceneLabel: `private:${entry.transcript_scene_id}`,
        ownerLabel: entry.owner_label || ownerId,
        summary: entry.summary || "该文件记录一个私聊对象的连续对话转录。",
      };
    }

    return {
      filePath: path.join(rootDir, "custom", `${String(entry.transcript_scene_id || "unknown")}.md`),
      scope: "custom",
      sceneLabel: `${entry.scene_type}:${entry.transcript_scene_id}`,
      ownerLabel: entry.owner_label || String(entry.owner_id || entry.transcript_scene_id || "unknown"),
      summary: entry.summary || "该文件记录一个自定义场景下的连续对话转录。",
    };
  }

  private async ensureHeader(
    filePath: string,
    target: { scope: string; sceneLabel: string; ownerLabel: string; summary: string }
  ): Promise<void> {
    try {
      await fs.access(filePath);
      return;
    } catch (_error) {
      const header = [
        "# Plugin Scene Transcript",
        `scope: ${target.scope}`,
        `scene: ${target.sceneLabel}`,
        `owner: ${target.ownerLabel}`,
        `summary: ${target.summary}`,
        "",
      ].join("\n");
      await fs.writeFile(filePath, header, "utf8");
    }
  }

  private formatEntry(entry: PluginSceneTranscriptEntry, content: string): string {
    const occurredAt = this.formatTimestamp(entry.occurred_at);
    const tags = Array.isArray(entry.tags) && entry.tags.length > 0
      ? ` [${entry.tags.join("/")}]`
      : "";
    return `- [${occurredAt}] ${entry.role} ${entry.speaker}:${tags} ${content}`.trim();
  }

  private normalizeContent(value: string): string {
    return String(value || "")
      .replace(/\r/g, "")
      .replace(/\n+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  private formatTimestamp(value?: string): string {
    const date = value ? new Date(value) : new Date();
    if (Number.isNaN(date.getTime())) {
      return String(value || "unknown-time");
    }
    return date.toISOString().replace("T", " ").replace(".000Z", "Z");
  }

  private async trimFile(filePath: string, maxLines: number): Promise<void> {
    const content = await fs.readFile(filePath, "utf8");
    const lines = content.split("\n");
    const headerLines: string[] = [];
    const entryLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith("- [")) {
        entryLines.push(line);
      } else if (line.length > 0 || headerLines.length > 0) {
        headerLines.push(line);
      }
    }

    if (entryLines.length <= maxLines) {
      return;
    }

    const trimmedEntries = entryLines.slice(entryLines.length - maxLines);
    const trimmed = [...headerLines, ...trimmedEntries, ""].join("\n");
    await fs.writeFile(filePath, trimmed, "utf8");
  }
}
