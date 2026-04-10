# Valheim BepInEx Modding — Distilled Wisdom

A reference guide for AI-assisted modding, based on hard-won experience building
`ScheduledMessages` and `EepyDeepy` from scratch on Linux.

---

## Environment Setup

### Toolchain
- **OS**: Linux (KDE Neon / Ubuntu-based tested)
- **SDK**: .NET 8 — install via `apt install dotnet-sdk-8.0`
- **Target framework**: `netstandard2.1` — do NOT use `net462` on Linux (requires Mono)
- **Build**: `dotnet build -c Release`
- **Decompiler**: `ilspycmd` — essential for inspecting Valheim DLLs

```bash
# Install ilspycmd
dotnet tool install ilspycmd -g

# Inspect a type
ilspycmd ~/.steam/steam/steamapps/common/Valheim/valheim_Data/Managed/assembly_valheim.dll -t Player | grep -i "emote"
```

### Project File (.csproj)
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.1</TargetFramework>
    <LangVersion>8.0</LangVersion>
    <MSBuildWarningsAsMessages>MSB3277</MSBuildWarningsAsMessages>
  </PropertyGroup>

  <PropertyGroup>
    <!-- Use server DLLs to avoid MSB3277 System.Net.Http conflict -->
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
    <!-- Add as needed -->
    <Reference Include="UnityEngine.AudioModule">
      <HintPath>$(ValheimDir)/valheim_server_Data/Managed/UnityEngine.AudioModule.dll</HintPath>
      <Private>false</Private>
    </Reference>
  </ItemGroup>
</Project>
```

### Build & Deploy Script
```bash
#!/bin/bash
set -e  # fail on build errors

VERSION=$(grep version_number ThunderstoreAssets/manifest.json | grep -o '[0-9]*\.[0-9]*\.[0-9]*')
MODNAME=$(basename "$PWD")
TARGET="/home/jason/.steam/debian-installation/steamapps/common/Valheim dedicated server"

dotnet build -c Release

cp bin/Release/netstandard2.1/${MODNAME}.dll "${TARGET}/BepInEx/plugins/"
cp *.cfg "${TARGET}/BepInEx/config/" 2>/dev/null || true

echo "Deployed ${MODNAME} v${VERSION}"
```

---

## BepInEx

### Installation (Linux dedicated server)
1. Download `BepInEx_unix_5.x.x.x.zip` from GitHub (NOT v6)
2. Extract into Valheim server root
3. Edit `run_bepinex.sh` — set `executable_name="valheim_server.x86_64"`
4. `chmod +x run_bepinex.sh`
5. Launch via `run_bepinex.sh` — never directly via the binary

### Key Paths
```
BepInEx/plugins/     ← DLL files go here
BepInEx/config/      ← Config files go here
BepInEx/LogOutput.log ← Full plugin log (more detail than console)
```

### Enable Console Logging
In `BepInEx/config/BepInEx.cfg`:
```ini
[Logging.Console]
Enabled = true

[Logging]
LogTimestamps = true
```

### Determining Server vs Client
```csharp
ZNet.instance.IsServer()      // true on dedicated server AND host
GUIManager.IsHeadless()       // true ONLY on dedicated server (requires Jotunn)
```

---

## Plugin Boilerplate

### GUID Convention
```
com.authorname.modname
e.g. com.byawn.eepydeepy
```

### Minimal Plugin
```csharp
[BepInPlugin(PluginGUID, PluginName, PluginVersion)]
public class MyPlugin : BaseUnityPlugin
{
    public const string PluginGUID    = "com.yourname.modname";
    public const string PluginName    = "ModName";
    public const string PluginVersion = "1.0.0";

    internal static ManualLogSource Log;
    internal static MyPlugin Instance;
    private Harmony harmony;

    private void Awake()
    {
        Log      = Logger;
        Instance = this;
        harmony  = new Harmony(PluginGUID);
        harmony.PatchAll();
        Log.LogInfo($"{PluginName} v{PluginVersion} loaded.");
    }

    private void OnDestroy()
    {
        harmony?.UnpatchSelf();
    }
}
```

---

## Harmony Patching

### Public Method
```csharp
[HarmonyPatch(typeof(Bed), nameof(Bed.Interact))]
public static class Patch_Bed_Interact
{
    static void Postfix(Humanoid human, bool __result)
    {
        if (!__result) return;
        // __result = return value of Interact()
        // human    = the parameter named 'human'
    }
}
```

### Private Method (use string name)
```csharp
[HarmonyPatch(typeof(Bed), "SetOwner")]
public static class Patch_Bed_SetOwner
{
    static void Postfix(long uid) { }
}
```

### Parameter Names Must Match
Harmony matches by parameter name. Always verify actual parameter names via ilspycmd:
```bash
ilspycmd assembly_valheim.dll -t Bed | grep -A5 "SetOwner"
```

### Common Pitfall: Hiding Unity Methods
`BaseUnityPlugin` inherits from `MonoBehaviour` which has its own `BroadcastMessage()`.
Naming your method the same causes CS0108. Rename yours to avoid the conflict.

---

## Sending Messages to Players

### ShowMessage (floating world-space text) — recommended
```csharp
ZRoutedRpc.instance.InvokeRoutedRPC(
    ZRoutedRpc.Everybody,
    "ShowMessage",
    (int)MessageHud.MessageType.Center,
    text
);
```

### ChatMessage RPC (appears in chat log)
Valheim validates the platform ID. Use `GetHostName()` with prefix handling:
```csharp
private string GetPlatformId(ZNetPeer peer)
{
    var rawId = peer.m_socket.GetHostName();
    if (rawId.StartsWith("Steam_") || rawId.StartsWith("playfab/"))
        return rawId;
    return "Steam_" + rawId;  // Windows Steam direct connection
}

ZRoutedRpc.instance.InvokeRoutedRPC(
    ZRoutedRpc.Everybody,
    "ChatMessage",
    new object[]
    {
        peer.m_refPos,
        (int)Talker.Type.Shout,
        "Server",
        GetPlatformId(peer),
        text
    }
);
```

> **WARNING**: This is a hack. The platform ID format varies by connection type
> (PlayFab relay vs direct Steam). Keep this code isolated in one method.

---

## Config Files

### Simple text format (no dependencies)
```
# Comment
timezone=10
welcome=Hello Vikings!
welcome-delay=30
09:00 Good morning!
23:30 Server restart in 30 minutes.
```

### Parsing
```csharp
foreach (string raw in File.ReadAllLines(configPath))
{
    string line = raw.Trim();
    if (string.IsNullOrEmpty(line) || line.StartsWith("#")) continue;

    if (line.StartsWith("timezone="))
        int.TryParse(line.Substring("timezone=".Length).Trim(), out timezone);
    else
    {
        int space = line.IndexOf(' ');
        if (space < 0) continue;
        string time = line.Substring(0, space).Trim();
        string text = line.Substring(space + 1).Trim();
    }
}
```

### Live Reload with Debounce
```csharp
private FileSystemWatcher configWatcher;
private DateTime lastConfigReload = DateTime.MinValue;

private void StartConfigWatcher()
{
    configWatcher = new FileSystemWatcher(Paths.ConfigPath, "mymod.cfg");
    configWatcher.NotifyFilter = NotifyFilters.LastWrite;
    configWatcher.Changed += OnConfigChanged;
    configWatcher.EnableRaisingEvents = true;
}

private void OnConfigChanged(object sender, FileSystemEventArgs e)
{
    if ((DateTime.Now - lastConfigReload).TotalSeconds < 1) return;
    lastConfigReload = DateTime.Now;
    System.Threading.Thread.Sleep(200);  // wait for file write to complete
    Log.LogInfo("Config reloaded.");
    LoadConfig();
}
```

> FileSystemWatcher fires twice on save (content + metadata). The 1-second debounce
> suppresses the duplicate.

---

## Jotunn RPCs

### When to use Jotunn
Use Jotunn RPCs when you need client↔server communication. Raw `ZRoutedRpc` works
for server→all-clients broadcasts but is painful for bidirectional flows.

### Dependency Declaration
```csharp
[BepInPlugin(PluginGUID, PluginName, PluginVersion)]
[BepInDependency(Jotunn.Main.ModGuid)]
public class MyPlugin : BaseUnityPlugin { }
```

### RPC Pattern: Client → Server → All Clients
```csharp
// Registration (in Awake)
clientToServerRPC = NetworkManager.Instance.AddRPC(
    "MyAction",
    RPC_OnMyAction,   // server handler
    RPC_NoOp          // client handler (unused)
);
serverToClientRPC = NetworkManager.Instance.AddRPC(
    "MyResult",
    RPC_NoOp,         // server handler (unused)
    RPC_OnMyResult    // client handler
);

// No-op helper
private IEnumerator RPC_NoOp(long sender, ZPackage package) { yield break; }

// Server handler
private IEnumerator RPC_OnMyAction(long sender, ZPackage package)
{
    ZNetPeer peer = ZNet.instance.GetPeer(sender);
    // do server-side logic
    serverToClientRPC.SendPackage(ZRoutedRpc.Everybody, new ZPackage());
    yield break;
}

// Client handler
private IEnumerator RPC_OnMyResult(long sender, ZPackage package)
{
    if (GUIManager.IsHeadless()) yield break;  // skip on dedicated server
    // do client-side logic (audio, UI, etc.)
    yield break;
}
```

### Sending RPCs
```csharp
// Client → Server
rpc.SendPackage(ZNet.instance.GetServerPeer().m_uid, new ZPackage());

// Server → All clients
rpc.SendPackage(ZRoutedRpc.Everybody, new ZPackage());
```

### Getting a Peer by Sender ID
```csharp
ZNetPeer peer = ZNet.instance.GetPeer(sender);
```

### Null handler caveat
Passing `null` as a handler to `AddRPC` causes a NullReferenceException inside
Jotunn when that side receives the RPC. Always use `RPC_NoOp` instead.

---

## Audio (Client Only)

### Loading OGG at runtime
```csharp
// Requires UnityEngine.AudioModule and UnityEngine.UnityWebRequestAudioModule references
private IEnumerator LoadAudio(string path)
{
    if (!File.Exists(path)) yield break;
    using (var req = UnityWebRequestMultimedia.GetAudioClip("file://" + path, AudioType.OGGVORBIS))
    {
        yield return req.SendWebRequest();
        if (req.result == UnityWebRequest.Result.Success)
            lullaby = DownloadHandlerAudioClip.GetContent(req);
    }
}
```

### Audio path relative to DLL
```csharp
string audioPath = Path.Combine(Path.GetDirectoryName(Info.Location), "lullaby.ogg");
```

### Convert MP3 to OGG
```bash
ffmpeg -y -i lullaby.mp3 -c:a libvorbis -q:a 4 lullaby.ogg
```

### Fade In/Out
```csharp
private IEnumerator FadeInMusic(float duration)
{
    float t = 0f;
    while (t < duration)
    {
        t += Time.deltaTime;
        audioSource.volume = Mathf.Clamp01(t / duration);
        yield return null;
    }
}
```

---

## Emote Patching

### Detected via Player.StartEmote
```csharp
[HarmonyPatch(typeof(Player), nameof(Player.StartEmote))]
public static class Patch_Player_StartEmote
{
    static void Postfix(string emote, Player __instance)
    {
        // Parameter is named 'emote', NOT 'name'
        if (emote != "rest") return;
        // fires on CLIENT
    }
}
```

### Stopped via Player.StopEmote (private)
```csharp
[HarmonyPatch(typeof(Player), "StopEmote")]
public static class Patch_Player_StopEmote
{
    static void Prefix(Player __instance)
    {
        // Player.LastEmote holds the name of the emote that just stopped
        if (Player.LastEmote != "rest") return;
        // StopEmote fires repeatedly while emote plays — debounce required
    }
}
```

> StopEmote is called every frame while an emote is active, not just once on exit.
> Use a flag or DateTime debounce.

---

## Bed Patching

```csharp
// Player gets into bed
[HarmonyPatch(typeof(Bed), nameof(Bed.Interact))]
static void Postfix(Humanoid human, bool __result)
{
    if (!ZNet.instance.IsServer() || !__result) return;
    // fires on SERVER
}

// Player leaves bed (uid == 0 means vacated)
[HarmonyPatch(typeof(Bed), "SetOwner")]
static void Postfix(long uid)
{
    if (!ZNet.instance.IsServer()) return;
    if (uid == 0) { /* bed vacated */ }
}

// Everyone slept successfully
[HarmonyPatch(typeof(EnvMan), "SkipToMorning")]
static void Postfix()
{
    if (!ZNet.instance.IsServer()) return;
    // sleep succeeded
}
```

---

## Thunderstore Publishing

### Package structure
```
mod.zip
├── manifest.json
├── README.md
├── icon.png          (256x256 PNG, required)
├── plugins/
│   └── MyMod.dll
└── config/
    └── mymod.cfg
```

### manifest.json
```json
{
    "name": "ModName",
    "version_number": "1.0.0",
    "website_url": "https://github.com/yourname/repo",
    "description": "Description, max 250 chars.",
    "dependencies": [
        "denikson-BepInExPack_Valheim-5.4.2333",
        "ValheimModding-Jotunn-2.24.3"
    ]
}
```

### Package build script
```bash
#!/bin/bash
set -e
rm -rf staging release
VERSION=$(grep version_number ThunderstoreAssets/manifest.json | grep -o '[0-9]*\.[0-9]*\.[0-9]*')
MODNAME=$(basename "$PWD")
mkdir -p staging/plugins staging/config release
cp ThunderstoreAssets/icon.png ThunderstoreAssets/README.md ThunderstoreAssets/manifest.json staging/
cp bin/Release/netstandard2.1/*.dll staging/plugins/
cp *.cfg staging/config/ 2>/dev/null || true
cd staging && zip -r ../release/tarbaby-${MODNAME}-${VERSION}.zip . && cd ..
rm -rf staging
echo "Built release/tarbaby-${MODNAME}-${VERSION}.zip"
```

---

## Known Gotchas

| Problem | Cause | Fix |
|---|---|---|
| `MSB3277` warning | Client DLL has newer `System.Net.Http` | Build against server DLLs, suppress with `<MSBuildWarningsAsMessages>MSB3277</MSBuildWarningsAsMessages>` |
| `CS0108` BroadcastMessage | Name clash with `Component.BroadcastMessage` | Rename your method |
| Emote patch parameter wrong | Parameter is `emote` not `name` | Use `string emote` |
| StopEmote fires repeatedly | Called every frame during emote | Debounce with flag or DateTime |
| FileSystemWatcher fires twice | Editor writes content then metadata | 1-second debounce on reload |
| Null RPC handler crash | Jotunn can't handle null handlers | Always use `RPC_NoOp` |
| ChatMessage validation fails | Wrong platform ID format | Use `GetPlatformId()` helper with Steam_ prefix logic |
| Audio only plays locally | Audio started client-side | Use RPC to tell all clients to play |
| Local server not found via PlayFab | NAT hairpin not supported by router | Connect via LAN IP directly; open UFW ports 2456-2457/udp |
| `netstandard2.1` Unity mismatch | Building against client vs server DLLs | Build against server — no warning |

---

## Useful ilspycmd Commands

```bash
# Find all methods on a type
ilspycmd assembly_valheim.dll -t ZNet | grep "public\|private\|protected"

# Find specific method
ilspycmd assembly_valheim.dll -t Player | grep -i "emote"

# Find RPC registrations
ilspycmd assembly_valheim.dll -t ZRoutedRpc | grep "Register\|Invoke"

# Find all methods with a keyword
ilspycmd assembly_valheim.dll -t Bed | grep -i "owner\|interact\|sleep"
```

---

## Debugging Tips

### Tail both logs simultaneously
```bash
multitail -s 2 \
  "path/to/server/BepInEx/LogOutput.log" \
  "path/to/client/BepInEx/LogOutput.log"
```

### Check if plugin loaded
Look for `Chainloader startup complete` then your plugin's load message in `LogOutput.log`.
The Valheim console output and BepInEx log are separate — always check `LogOutput.log`.

### Check if RPC fired
Add log lines at every RPC entry point. If a handler never logs, the RPC was never received.

### Verify DLL is deployed
```bash
ls -la BepInEx/plugins/
# Check timestamp matches your build time
```
