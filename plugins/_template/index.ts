/**
 * 插件入口 — index.ts
 *
 * 【必须存在】导出插件实例单例。
 * PluginManager 通过 require(path).default 加载此文件。
 *
 * 规范：
 *   - 此文件只做一件事：实例化并导出插件类
 *   - 不要在此文件里写任何业务逻辑
 */
import { MyPlugin } from './src/my-plugin';

export default new MyPlugin();
