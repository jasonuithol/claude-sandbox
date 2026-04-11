# Valheim Modding — Harmony Patching

---

## Public Method Patch

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

---

## Private Method Patch (use string name)

Harmony resolves overloads by parameter types. For private methods you can't reference
with `nameof()`, pass the name as a string:

```csharp
[HarmonyPatch(typeof(Bed), "SetOwner")]
public static class Patch_Bed_SetOwner
{
    static void Postfix(long uid) { }
}

[HarmonyPatch(typeof(EnvMan), "OnMorning")]         // private
[HarmonyPatch(typeof(SleepText), "ShowDreamText")]  // private
[HarmonyPatch(typeof(Player), "AddKnownBiome")]     // private
```

Always decompile first to confirm the exact name and parameter signature.

---

## Patching the ZRoutedRpc Constructor

`ZRoutedRpc` is a plain class, not a MonoBehaviour — it has no `Awake()`. Patch the
constructor instead. This fires on both server and client when `ZRoutedRpc` initialises.

```csharp
[HarmonyPatch(typeof(ZRoutedRpc), MethodType.Constructor, new[] { typeof(bool) })]
private static class ZRoutedRpc_Ctor_Patch
{
    static void Postfix()
    {
        ZRoutedRpc.instance.Register<string>("MyMod_MyRPC", RPC_Handler);
    }
}
```

---

## Prefix to Suppress the Original

Returning `false` from a Prefix completely skips the original method. Use this to
suppress skill loss, tombstone creation, item discovery notifications, dream text,
"good morning" messages, etc.:

```csharp
[HarmonyPatch(typeof(Player), "AddKnownBiome")]
static class Patch_SuppressBiomeDisovery
{
    static bool Prefix()
    {
        if (IsEventActive || IsEventStarting) return false; // skip original
        return true; // run original
    }
}
```

---

## Parameter Names Must Match Exactly

Harmony matches parameters by name, not just type. A wrong name silently fails to inject.
`nameof()` won't compile for protected/private members. **Always decompile before writing a patch.**

```bash
ilspycmd assembly_valheim.dll -t Player | grep -A 10 "StartEmote"
ilspycmd assembly_valheim.dll -t Bed    | grep -A 10 "Interact"
```

Example of a subtle name difference:
```csharp
// WRONG — parameter is not named 'name'
static void Postfix(string name, Player __instance) { }

// CORRECT — decompile confirms parameter is 'emote'
static void Postfix(string emote, Player __instance) { }
```

---

## Common Name Clash: BroadcastMessage

`BaseUnityPlugin` inherits from `MonoBehaviour`, which has its own `BroadcastMessage(string)`.
Naming your method the same causes CS0108. Rename yours:

```csharp
// ❌ Clashes with Component.BroadcastMessage
private void BroadcastMessage(string text) { }

// ✅ No clash
private void SendServerBroadcast(string text) { }
```

---

## Bed Patching Pattern

```csharp
// Player gets into bed
[HarmonyPatch(typeof(Bed), nameof(Bed.Interact))]
static class Patch_Bed_Interact
{
    static void Postfix(Humanoid human, bool __result)
    {
        if (!ZNet.instance.IsServer() || !__result) return;
        // fires on SERVER when interaction succeeds
    }
}

// Player leaves bed (uid == 0 means vacated)
[HarmonyPatch(typeof(Bed), "SetOwner")]
static class Patch_Bed_SetOwner
{
    static void Postfix(long uid)
    {
        if (!ZNet.instance.IsServer()) return;
        if (uid == 0) { /* bed vacated */ }
    }
}

// Everyone slept successfully
[HarmonyPatch(typeof(EnvMan), "SkipToMorning")]
static class Patch_EnvMan_SkipToMorning
{
    static void Postfix()
    {
        if (!ZNet.instance.IsServer()) return;
        // sleep succeeded — all players in bed
    }
}
```

---

## Emote Patching Pattern

```csharp
// StartEmote fires once when an emote begins
[HarmonyPatch(typeof(Player), nameof(Player.StartEmote))]
static class Patch_Player_StartEmote
{
    static void Postfix(string emote, Player __instance)
    {
        // parameter is 'emote', NOT 'name'
        if (emote != "rest") return;
        // fires on CLIENT
    }
}

// StopEmote fires EVERY FRAME while an emote is active — debounce required
[HarmonyPatch(typeof(Player), "StopEmote")]
static class Patch_Player_StopEmote
{
    static void Prefix(Player __instance)
    {
        // Player.LastEmote holds the name of the emote that just stopped
        if (Player.LastEmote != "rest") return;
        // debounce: use a flag or DateTime check
    }
}
```
