/**
 * 榛樿閰嶇疆妯℃澘
 * 鐢ㄤ簬棣栨杩愯鎴栧懡浠よ宸ュ叿鐢熸垚瀹屾暣鐨勫甫娉ㄩ噴 YAML 閰嶇疆鏂囦欢銆?
 *
 * 璋冪敤鍏ュ彛锛欳onfigManager.generateDefaults()
 */

/** system.yaml 鈥?绯荤粺绾ч厤缃紙鍚堝苟鍘?app + kernel锛?*/
export const SYSTEM_YAML_TEMPLATE = `# 鈺斺晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晽
# 鈺? Cradle Selrena 鈥?绯荤粺閰嶇疆 (system.yaml)                  鈺?
# 鈺? 绔彛鍙?/ IPC 閫氫俊 / 鏃ュ織绾у埆 / 妯″潡鐢熷懡鍛ㄦ湡 / 鎻掍欢娌欑    鈺?
# 鈺氣晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨暆

# 搴旂敤鏄剧ず鍚嶇О
app_name: "Cradle Selrena"

# 璇箟鍖栫増鏈彿锛堜粎灞曠ず锛屼笉褰卞搷杩愯琛屼负锛?
app_version: "0.1.0"

# 鍏ㄥ眬鏃ュ織绾у埆锛歞ebug | info | warn | error
log_level: "debug"

# 鈹€鈹€ 鐩綍璺緞锛堝潎鐩稿浜庨」鐩牴鐩綍锛?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

# 鎸佷箙鍖栨暟鎹洰褰曪紙鏁版嵁搴撱€佽蹇嗙瓑锛?
data_dir: "data"

# 鏃ュ織杈撳嚭鐩綍
log_dir: "logs"

# 鑷姩澶囦唤瀛樻斁鐩綍
backup_dir: "data/backup"

# 鑷姩澶囦唤闂撮殧锛堝皬鏃讹級锛? = 涓嶅浠?
auto_backup_interval_hours: 24

# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣
#  ipc 鈥?TS 鈫?Python 杩涚▼闂撮€氫俊
# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣

ipc:
  bind_address: "tcp://127.0.0.1:8765" # ZMQ 缁戝畾鍦板潃
  request_timeout_ms: 30000            # 鍗曟璇锋眰瓒呮椂锛坢s锛?
  retry_count: 2                       # 璇锋眰澶辫触閲嶈瘯娆℃暟
  retry_interval_ms: 2000              # 閲嶈瘯闂撮殧锛坢s锛?
  heartbeat_interval_ms: 5000          # Python 蹇冭烦妫€娴嬮棿闅旓紙ms锛?

# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣
#  lifecycle 鈥?妯″潡鍚仠椤哄簭
# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣

lifecycle:
  start_timeout_ms: 30000
  stop_timeout_ms: 30000
  module_start_order:
    - config
    - persistence
    - ipc
    - python_ai
    - extensions
    - life_clock
  module_stop_order:
    - life_clock
    - extensions
    - python_ai
    - ipc
    - persistence
    - config

# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣
#  extension - 扩展系统
# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣

extension:
  extension_root_dir: "extensions"
  sandbox:
    enable_isolation: true
    timeout_ms: 5000
    allow_native_modules: false
  default_permissions:
    - CHAT_SEND
    - MEMORY_READ
    - MEMORY_WRITE
    - CONFIG_READ_SELF
    - CONFIG_WRITE_SELF
    - CONFIG_READ_GLOBAL
    - EVENT_SUBSCRIBE
  extension_blacklist: []
`;

/** persona.yaml 鈥?瑙掕壊浜烘牸涓?AI 灞傞厤缃?*/
export const PERSONA_YAML_TEMPLATE = `# 鈺斺晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晽
# 鈺? Cradle Selrena 鈥?浜鸿閰嶇疆 (persona.yaml)                 鈺?
# 鈺? 鍖呭惈浜烘牸瀹氫箟 / 鎺ㄧ悊鍙傛暟 / LLM 鎻愪緵鍟嗛厤缃?                 鈺?
# 鈺? 鈿?鏈枃浠剁粨鏋勪负 TS鈫擯ython IPC 濂戠害锛岃鍕块殢鎰忓彉鏇村眰绾?      鈺?
# 鈺氣晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨暆

# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣
#  persona 鈥?瑙掕壊浜烘牸瀹氫箟
# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣

persona:
  # 鈹€鈹€ 鍩虹妗ｆ 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
  # 鍙繚鐣欐渶灏忚韩浠介敋瀹氾紝鎬ф牸/澶栬/椋庢牸绛変汉鏍艰鑲夊畬鍏ㄧ敱 knowledge-base.json 鎵胯浇
  base:
    name: "Selrena"                    # 瑙掕壊姝ｅ紡鍚嶏紙鑻辨枃锛?
    nickname: "鏈堣"                   # 瑙掕壊鏄电О锛堜腑鏂囷級

  # 鈹€鈹€ 浜烘牸妯″紡 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
  # api          鈫?鐭ヨ瘑搴撴彁渚涙墍鏈夐鏍煎紩瀵?+ minimal 鎻愮ず璇嶉敋瀹?
  # local_base   鈫?鍚?api锛堜娇鐢ㄦ湰鍦板熀纭€妯″瀷锛屾棤涓撻」寰皟锛?
  # local_finetune 鈫?璇磋瘽椋庢牸宸茬儤鐒欏埌鏉冮噸锛岃烦杩囦汉璁剧煡璇嗗簱妫€绱紝浣跨敤鏋佺畝鎻愮ず璇?
  persona_mode: "api"

  # 鈹€鈹€ 瀹夊叏绛栫暐 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
  safety:
    taboos: ""                         # 绂佸繉瑙勫垯锛堣嚜鐢辨枃鏈級
    forbidden_phrases: []              # 涓ユ牸绂佹鍑虹幇鐨勭煭璇?
    forbidden_regex: []                # 绂佹鍖归厤鐨勬鍒欒〃杈惧紡

# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣
#  inference 鈥?鎺ㄧ悊寮曟搸鍙傛暟
# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣

inference:
  # 鈹€鈹€ 妯″瀷鍙傛暟 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
  model:
    local_model_path: ""               # 鏈湴妯″瀷璺緞锛堜粎 api_type=local 鏃剁敓鏁堬級
    max_tokens: 1024                   # 鍗曟鐢熸垚鏈€澶?token 鏁?
    temperature: 0.8                   # 閲囨牱娓╁害锛?=纭畾鎬?~ 2=鏈€澶ч殢鏈猴級
    top_p: 0.9                         # 鏍搁噰鏍锋鐜囬槇鍊?
    frequency_penalty: 0.0             # 棰戠巼鎯╃綒鍥犲瓙锛?2 ~ 2锛?

  # 鈹€鈹€ 鐢熷懡鏃堕挓 / 娉ㄦ剰鍔涚鐞?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
  life_clock:
    focused_interval_ms: 10000         # 鐒︾偣妯″紡蹇冭烦闂撮殧锛坢s锛?
    ambient_interval_ms: 45000         # 鐜妯″紡蹇冭烦闂撮殧锛坢s锛?
    default_mode: "standby"            # 鍚姩鏃堕粯璁ゆā寮忥細standby | ambient | focused
    focus_duration_ms: 20000           # 鐒︾偣瓒呮椂鏃堕暱锛坢s锛夛紝瓒呮椂鍚庡洖钀藉埌榛樿妯″紡
    ingress_debounce_ms: 1400          # 鏅€氭秷鎭槻鎶栫獥鍙ｏ紙ms锛?
    ingress_focused_debounce_ms: 700   # 鐒︾偣妯″紡闃叉姈绐楀彛锛坢s锛?
    ingress_max_batch_messages: 4      # 鍗曟壒娆℃渶澶ф秷鎭潯鏁?
    ingress_max_batch_items: 24        # 鍗曟壒娆℃渶澶у獟浣撻」鏁?
    summon_keywords:                   # 鍞ら啋鍏抽敭璇嶅垪琛?
      - "鏈堣"
      - "selrena"
    focus_on_any_chat: false           # true = 浠绘剰娑堟伅閮借Е鍙戠劍鐐癸紙鏃犻渶鍞ら啋璇嶏級
    active_thought_modes: []           # 鍏佽涓诲姩鎬濈淮鐨勬ā寮忓垪琛紙绌?= 绂佺敤锛?
    # 娉ㄦ剰锛氭潵婧愮被鍨嬬殑娉ㄦ剰鍔涚瓥鐣ワ紙source_focus_policies锛夌敱鍚?Vessel 鎻掍欢鑷娉ㄥ唽锛屼笉鍦ㄦ澶勯厤缃?

  # 鈹€鈹€ 瀵硅瘽璁板繂瑙勫垯 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
  memory:
    max_recall_count: 5                # 鍗曟妫€绱㈡渶澶ц蹇嗘潯鏁?
    retention_days: 30                 # 璁板繂淇濈暀澶╂暟
    context_limit: 6                   # 鎻愮ず璇嶄腑鎼哄甫鐨勫巻鍙叉潯鏁颁笂闄?
    conversation_window: 12            # 瑙﹀彂鎽樿鍓嶇殑鏈€澶у璇濊疆鏁?
    summary_trigger_count: 18          # 瑙﹀彂鑷姩鎽樿鐨勬秷鎭潯鏁?
    summary_keep_recent_count: 6       # 鎽樿鏃朵繚鐣欑殑鏈€杩戞秷鎭暟
    summary_max_chars: 2400            # 鎽樿鏂囨湰鏈€澶у瓧绗︽暟

  # 鈹€鈹€ 澶氭ā鎬佸鐞?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
  multimodal:
    enabled: false                     # 鏄惁鍚敤澶氭ā鎬佽緭鍏?
    strategy: "specialist_then_core"   # core_direct | specialist_then_core
    max_items: 6                       # 鍗曟鏈€澶у獟浣撻」
    core_model: "deepseek/chat"        # 涓绘帹鐞嗘ā鍨嬶紙provider/alias 鏍煎紡锛?
    image_model: ""                    # 鍥惧儚涓撳妯″瀷锛堝 qwen/vision锛?
    video_model: ""                    # 瑙嗛涓撳妯″瀷

  # 鈹€鈹€ 鍔ㄤ綔娴侊紙Live2D 鑱斿姩锛?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
  action_stream:
    enabled: false                     # 鏄惁鍚敤鍔ㄤ綔娴?
    channel: "live2d"                  # 娓叉煋閫氶亾

# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣
#  llm 鈥?LLM 鎻愪緵鍟嗛厤缃?
#  API Key 浼樺厛浠?secret/secrets.yaml 鑷姩娉ㄥ叆锛屾澶勫彲鐣欑┖
# 鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣

llm:
  api_type: "deepseek"                 # 涓?API 鍗忚锛歰penai | azure | anthropic | deepseek | local
  base_url: "https://api.deepseek.com" # 涓?API 绔偣
  temperature: 0.7                     # 涓婚噰鏍锋俯搴?
  # api_key: ""                        # 鐣欑┖锛岀敱 secrets.yaml 娉ㄥ叆
  models:
    chat: "deepseek-chat"              # 榛樿妯″瀷锛坧rovider_key=None 鏃朵娇鐢級

  # 澶氭彁渚涘晢閰嶇疆锛堟寜闇€娣诲姞锛?
  # provider_key 鏍煎紡锛?
  #   "deepseek"      鈫?providers.deepseek.models 绗竴涓ā鍨?
  #   "deepseek/chat" 鈫?providers.deepseek.models.chat
  # providers:
  #   deepseek:
  #     api_type: "deepseek"
  #     base_url: "https://api.deepseek.com"
  #     temperature: 0.7
  #     models:
  #       chat: "deepseek-chat"
  #   qwen:
  #     api_type: "openai"
  #     base_url: "https://dashscope.aliyuncs.com/compatible-mode"
  #     temperature: 0.7
  #     models:
  #       text: "qwen3.5-plus"
  #       vision: "qwen-vl-max"
`;

/** secret/secrets.example.yaml 鈥?鏁忔劅淇℃伅绀轰緥鏂囦欢 */
export const SECRETS_EXAMPLE_YAML_TEMPLATE = `# 鈺斺晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晽
# 鈺? 鏁忔劅淇℃伅閰嶇疆锛堣鍕挎彁浜ゅ埌鐗堟湰鎺у埗锛?                       鈺?
# 鈺? 澶嶅埗鏈枃浠朵负 secrets.yaml 骞跺～鍏ョ湡瀹炲嚟鎹?                 鈺?
# 鈺氣晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨暆

# LLM API Key锛堟寜鎻愪緵鍟嗗悕绉拌嚜鍔ㄦ敞鍏ュ埌 persona.yaml 涓級
providers:
  deepseek:
    api_key: "sk-..."
  qwen:
    api_key: "sk-..."
  openai:
    api_key: "sk-..."

# NapCat 閫傞厤鍣ㄥ嚟鎹?
napcat:
  token: ""
`;

/** active-extensions.yaml - 启用的扩展列表 */
export const ENABLED_EXTENSIONS_YAML_TEMPLATE = `# 启用的扩展列表（按数组顺序加载）
enabled_extensions: []
`;

