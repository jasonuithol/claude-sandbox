# Valheim Modding Knowledge Base

## Environment

- **Server OS**: Linux (Ubuntu)
- **Valheim dedicated server**: `~/.steam/steam/steamapps/common/Valheim dedicated server`
- **BepInEx dir**: `$(ValheimDir)/BepInEx`
- **Game assemblies**: `$(ValheimDir)/valheim_server_Data/Managed/`
- **BepInEx log**: `$(ValheimDir)/BepInEx/LogOutput.log`
- **Target framework**: `netstandard2.1`
- **LangVersion**: `8.0`

---

## csproj Template

Keep it simple. Direct `<Reference>` includes, no NuGet packages, no custom `OutputPath` (MCP service has a deploy command).

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.1</TargetFramework>
    <AssemblyName>MyMod</AssemblyName>
    <RootNamespace>MyMod</RootNamespace>
    <LangVersion>8.0</LangVersion>
  </PropertyGroup>
  <PropertyGroup>
    <ValheimDir>$(HOME)/.steam/steam/steamapps/common/Valheim dedicated server</ValheimDir>
    <BepInExDir>$(ValheimDir)/BepInEx</BepInExDir>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="BepInEx">
      <HintPath>$(BepInExDir)/core/BepInEx.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="0Harmony">
      <HintPath>$(BepInExDir)/core/0Harmony.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="assembly_valheim">
      <HintPath>$(ValheimDir)/valheim_server_Data/Managed/assembly_valheim.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="UnityEngine">
      <HintPath>$(ValheimDir)/valheim_server_Data/Managed/UnityEngine.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="UnityEngine.CoreModule">
      <HintPath>$(ValheimDir)/valheim_server_Data/Managed/UnityEngine.CoreModule.dll</HintPath>
      <Private>false</Private>
    </Reference>
  </ItemGroup>
</Project>
```

**Notes**:
- `PluginGUID` determines the config filename — set it to something simple like `"raindance"` to get `raindance.cfg` instead of `com.yourname.raindance.cfg`
- Do NOT add `UnityEngine.AnimationModule` unless you actually use `Animator` directly — and avoid `Animator.StringToHash` where possible, prefer ZDOVars constants

---

## Plugin Boilerplate

```csharp
[BepInPlugin(PluginGUID, PluginName, PluginVersion)]
public class MyPlugin : BaseUnityPlugin
{
    public const string PluginGUID    = "myplugin";
    public const string PluginName    = "MyPlugin";
    public const string PluginVersion = "1.0.0";

    internal static ManualLogSource Log;
    private Harmony _harmony;

    void Awake()
    {
        Log = Logger;
        _harmony = new Harmony(PluginGUID);
        _harmony.PatchAll();
        Log.LogInfo("MyPlugin loaded.");
    }

    void OnDestroy() => _harmony?.UnpatchSelf();
}
```

---

## Server vs Client Detection

```csharp
// In Update() — guard all server logic with this
if (ZNet.instance == null || !ZNet.instance.IsServer()) return;
```

The dedicated server runs the same assembly as the client. `IsServer()` is how you branch. Both server and client run `Awake()` and can register RPC handlers.

---

## Peer Iteration (Server-Side)

```csharp
foreach (var peer in ZNet.instance.GetPeers())
{
    if (peer.m_uid == 0) continue; // skip ghost peers

    ZDO zdo = ZDOMan.instance.GetZDO(peer.m_characterID);
    if (zdo == null) continue;

    // peer.m_playerName  — display name
    // peer.m_uid         — unique peer ID (long)
    // peer.m_refPos      — player's world position
    // peer.m_socket.GetHostName() — platform ID e.g. "playfab/XXX" or "76561XXXXXX"
}
```

**Cleanup pattern for Dictionary keyed by peer UID**:
```csharp
var connected = new HashSet<long>(ZNet.instance.GetPeers().Select(p => p.m_uid));
foreach (var uid in myDict.Keys.Where(uid => !connected.Contains(uid)).ToList())
    myDict.Remove(uid);
```

---

## ZDO Reading (Server-Side Player State)

ZDOs are the networked state objects for every entity. Players sync their state here and the server can read it.

### Emote Detection
```csharp
// s_emote is stored as a plain STRING — not a hash
string emoteName = zdo.GetString(ZDOVars.s_emote); // e.g. "dance", "wave", "sit", "" when idle
bool isDancing = emoteName == "dance";
```

### Equipment Detection
```csharp
// Equipment is stored as INT (name.GetStableHashCode()) — NOT a string
int rightItemHash = zdo.GetInt(ZDOVars.s_rightItem);
if (rightItemHash != 0)
{
    GameObject prefab = ZNetScene.instance?.GetPrefab(rightItemHash);
    ItemDrop itemDrop = prefab?.GetComponent<ItemDrop>();
    Skills.SkillType skill = itemDrop?.m_itemData.m_shared.m_skillType ?? Skills.SkillType.None;
    bool isAxe = skill == Skills.SkillType.Axes;
}
```

### ZDOVars Quick Reference
```csharp
ZDOVars.s_emote          // string — current emote name, "" when idle
ZDOVars.s_emoteID        // int — counter, increments each emote start/stop
ZDOVars.s_emoteOneshot   // bool
ZDOVars.s_rightItem      // int hash — right hand item prefab name hash
ZDOVars.s_leftItem       // int hash
ZDOVars.s_helmetItem     // int hash
ZDOVars.s_chestItem      // int hash
ZDOVars.s_legItem        // int hash
ZDOVars.s_shoulderItem   // int hash
```

### ⚠️ ZSyncAnimation Salt Warning
Animator parameters synced via `ZSyncAnimation` use a salt: `438569 + Animator.StringToHash(paramName)`.
**However**, emotes do NOT go through `ZSyncAnimation` — they write directly to ZDO via `ZDOVars`. Don't apply the salt to emote keys.

---

## Messaging — The Right Way

### ✅ ShowMessage (use this)
Sends a HUD message to all clients. Clean, no platform ID needed.

```csharp
private static void ShowMessage(MessageHud.MessageType type, string text)
{
    if (string.IsNullOrWhiteSpace(text)) return;
    if (ZRoutedRpc.instance == null) return;

    ZRoutedRpc.instance.InvokeRoutedRPC(
        ZRoutedRpc.Everybody,
        "ShowMessage",
        (int)type,
        text);
}

// Usage
ShowMessage(MessageHud.MessageType.Center, "Big dramatic message");   // centre screen
ShowMessage(MessageHud.MessageType.TopLeft, "Subtle notification");   // top left
```

### ❌ ChatMessage (avoid)
Requires a real peer's platform ID or it throws `EndOfStreamException`. Signature:
```csharp
// (Vector3 pos, int talkerType, string senderName, string platformUserID, string text)
// platformUserID must be a real connected peer's ID — fragile, avoid
```

If you must use `ChatMessage` (e.g. to send to a specific player as "from" them), get the platform ID like this:
```csharp
private static string GetPlatformId(ZNetPeer peer)
{
    var rawId = peer.m_socket.GetHostName();
    if (rawId.StartsWith("Steam_") || rawId.StartsWith("playfab/"))
        return rawId;
    return "Steam_" + rawId;
}
```

---

## Custom RPCs (Server → Client)

Use this when you need to trigger something on clients that has no built-in RPC (e.g. setting local weather).

### Registration — Harmony patch on ZRoutedRpc.Awake
Both server and client run `Awake`, so both register the handler. Server only sends, client only receives.

```csharp
[HarmonyPatch(typeof(ZRoutedRpc), nameof(ZRoutedRpc.Awake))]
private static class ZRoutedRpc_Awake_Patch
{
    static void Postfix()
    {
        ZRoutedRpc.instance.Register<string>("MyMod_MyRPC", RPC_Handler);
    }
}

private static void RPC_Handler(long sender, string payload)
{
    // runs on client when server calls BroadcastRPC
}
```

### Sending from Server
```csharp
private static void BroadcastRPC(string payload)
{
    ZRoutedRpc.instance.InvokeRoutedRPC(
        ZRoutedRpc.Everybody,
        "MyMod_MyRPC",
        payload);
}
```

**Naming**: prefix RPC names with your mod name to avoid collisions with other mods e.g. `"RainDance_SetWeather"`.

---

## What IS and IS NOT Synced Server → Client

### ✅ Synced (server controls these)
| RPC | Signature | Effect |
|-----|-----------|--------|
| `ShowMessage` | `(int type, string text)` | HUD message on all clients |
| `SetEvent` | `(string name, float time, Vector3 pos)` | Random raid event |
| `SpawnObject` | `(Vector3 pos, Quaternion rot, int prefabHash)` | Spawn entity |
| `RPC_TeleportPlayer` | `(Vector3 pos, Quaternion rot, bool distant)` | Teleport player |
| `SetGlobalKey` / `RemoveGlobalKey` | `(string name)` | Progression flags |
| `SleepStart` / `SleepStop` | none | Force sleep |
| `NetTime` | `(double time)` | Game time |

### ❌ NOT Synced (client-local only)
- **`EnvMan`** — weather/environment. Each client runs its own independently. `SetForceEnvironment()` on the server only affects the server process (no player there). Use a custom RPC to call it on clients.
- **`AudioMan`** — ambient sound
- **`MusicMan`** — music
- **`Hud`** — HUD elements (use `ShowMessage` RPC instead)
- **`MessageHud`** (direct) — use `ShowMessage` RPC instead
- **`PostProcessing`** — screen effects

---

## Weather / EnvMan

```csharp
// Force an environment (call on the local instance — server or client)
EnvMan.instance.SetForceEnvironment("Rain");        // Light rain
EnvMan.instance.SetForceEnvironment("ThunderStorm"); // Storm + lightning
EnvMan.instance.SetForceEnvironment("");             // Clear override, return to natural

// DON'T set m_forceEnv directly — use SetForceEnvironment() which also
// triggers FixedUpdate() and ReflectionUpdate immediately
```

**Valid environment names** (from `m_environments` list, loaded from assets):
`"Rain"`, `"ThunderStorm"`, `"LightRain"`, `"DeepForest_Mist"`, `"Ashrain"`, plus biome-specific ones.

**To force weather on all clients**: send a custom RPC (see above) — clients call `SetForceEnvironment` on their local `EnvMan`.

---

## Config

### BepInEx Config.Bind (simple, auto-generates .cfg)
```csharp
private ConfigEntry<float>  _myFloat;
private ConfigEntry<string> _myString;

// In Awake():
_myFloat = Config.Bind("SectionName", "KeyName", 10f, "Description");
_myString = Config.Bind("Messages", "RainMessage", "It is raining!", "Shown when rain starts.");

// Usage:
float val = _myFloat.Value;
string msg = _myString.Value;
```
Config file is named after `PluginGUID` — keep GUID simple.

### Manual .cfg with FileSystemWatcher (for custom format)
See `ScheduledMessages` mod for a full implementation. Good for non-standard formats like `HH:MM message` scheduled entries.

---

## ILSpy — Decompiling Game Assemblies

Essential for figuring out real field names, method signatures, and ZDO key names.

```bash
# Install
dotnet tool install ilspycmd -g

# Decompile a specific class
ilspycmd "$HOME/.steam/steam/steamapps/common/Valheim dedicated server/valheim_server_Data/Managed/assembly_valheim.dll" -t ClassName

# Filter output — use grep for large classes
ilspycmd "...assembly_valheim.dll" -t EnvMan | grep -A 5 -i "force\|environ"

# Find all RPC registrations
ilspycmd "...assembly_valheim.dll" | grep "Register\|InvokeRoutedRPC" | sort -u

# Find ZDOVars constants
ilspycmd "...assembly_valheim.dll" -t ZDOVars | grep -i "emote\|item\|equip"
```

**Key classes to know**:
- `ZDOVars` — all ZDO key constants (as `int` hashes of strings)
- `ZRoutedRpc` — all routed RPC registrations and invocations
- `EnvMan` — weather/environment system
- `ZSyncAnimation` — animator parameter sync (uses salt `438569 + hash`)
- `VisEquipment` — equipment visual sync (stores as int hash, NOT string)
- `Player` — emote logic, `StartEmote`, `StopEmote`, `UpdateEmote`
- `ZNetPeer` — peer fields: `m_uid`, `m_playerName`, `m_characterID`, `m_refPos`, `m_socket`
- `RandEventSystem` — random event/raid system

---

## Common Gotchas

1. **`~` doesn't expand in double-quoted bash strings** — use `$HOME` instead
   ```bash
   TARGET="$HOME/.steam/..."  # ✅
   TARGET="~/.steam/..."      # ❌
   ```

2. **Equipment ZDO values are int hashes, not strings**
   ```csharp
   zdo.GetString(ZDOVars.s_rightItem) // always returns "" ❌
   zdo.GetInt(ZDOVars.s_rightItem)    // returns hash ✅
   ```

3. **Emote ZDO value IS a string** (exception to above)
   ```csharp
   zdo.GetString(ZDOVars.s_emote) // returns "dance", "wave" etc ✅
   ```

4. **`BroadcastMessage` name clash** — `Component` (Unity base class) has a `BroadcastMessage(string)` method. Don't name your methods `BroadcastMessage` or you'll get CS0108. Use `SendServerBroadcast`, `ShowMessage`, etc.

5. **`ChatMessage` RPC needs a real platform ID** — use `ShowMessage` instead for server announcements.

6. **`SetForceEnvironment` not `m_forceEnv`** — the method also triggers immediate update; direct field assignment does not.

7. **Ghost peers** — always skip `peer.m_uid == 0`

8. **ZSyncAnimation salt** — animator params on ZDO use `438569 + Animator.StringToHash(name)` as the key. Emotes do NOT use this — they go directly via `ZDOVars`.

9. **`mkdir -p` before `cp`** in deploy scripts — BepInEx `plugins/` subdirectory may not exist on first deploy.
