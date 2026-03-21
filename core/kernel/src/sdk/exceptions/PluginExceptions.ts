export class PluginLoadError extends Error {
  constructor(msg: string) { super(msg); this.name = "PluginLoadError"; }
}
export class ChannelAdapterError extends Error {
  constructor(msg: string) { super(msg); this.name = "ChannelAdapterError"; }
}
