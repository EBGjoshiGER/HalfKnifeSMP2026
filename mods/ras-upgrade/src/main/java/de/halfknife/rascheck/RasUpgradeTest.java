package de.halfknife.rascheck;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import com.mojang.authlib.GameProfile;
import tn.nightbeam.ras.platform.Services;
import tn.nightbeam.ras.network.PlayerVariables;
import tn.nightbeam.ras.util.AttributeManager;
import java.util.*;

/** Disposable isolated-server tests only; this class is never added to the production RAS JAR. */
public final class RasUpgradeTest implements ModInitializer {
    @Override public void onInitialize() { ServerLifecycleEvents.SERVER_STARTED.register(RasUpgradeTest::check); }
    private static void check(MinecraftServer server) {
        try {
            ServerPlayer player = null;
            for (var constructor : ServerPlayer.class.getConstructors()) {
                Object[] args = new Object[constructor.getParameterCount()];
                boolean supported = true;
                for (int i = 0; i < args.length; i++) {
                    Class<?> type = constructor.getParameterTypes()[i];
                    if (type.isInstance(server)) args[i] = server;
                    else if (type.isInstance(server.overworld())) args[i] = server.overworld();
                    else if (type == GameProfile.class) args[i] = new GameProfile(UUID.randomUUID(), "RasUpgradeTest");
                    else if (type.getSimpleName().equals("ClientInformation")) args[i] = type.getMethod("createDefault").invoke(null);
                    else supported = false;
                }
                if (supported) { player = (ServerPlayer)constructor.newInstance(args); break; }
            }
            if (player == null) throw new AssertionError("Unsupported ServerPlayer constructor");
            PlayerVariables vars = Services.PLATFORM.getPlayerVariables(player);
            var events = Class.forName("tn.nightbeam.ras.events.FabricRpgAttributeSystemModEvents");
            var locked = events.getDeclaredMethod("isItemLocked", ItemStack.class, Player.class); locked.setAccessible(true);
            for (String key : AttributeManager.ATTRIBUTE_IDS) vars.attributes.put(key, 99999.0);
            vars.Level = 11;
            if (!(Boolean)locked.invoke(null, new ItemStack(Items.DIAMOND_SWORD), player)) throw new AssertionError("High attribute values bypassed global level 12");
            vars.Level = 12; vars.attributes.replaceAll((k,v) -> 0.0);
            if ((Boolean)locked.invoke(null, new ItemStack(Items.DIAMOND_SWORD), player)) throw new AssertionError("Diamond did not unlock at global level 12");
            vars.Level = 29;
            if (!(Boolean)locked.invoke(null, new ItemStack(Items.NETHERITE_HELMET), player)) throw new AssertionError("Netherite unlocked below 30");
            vars.Level = 30;
            if ((Boolean)locked.invoke(null, new ItemStack(Items.NETHERITE_HELMET), player)) throw new AssertionError("Netherite did not unlock at 30");
            vars.SparePoints = 3;
            var allocation = Class.forName("tn.nightbeam.ras.procedures.AddPointsAttributeGenericProcedure")
                .getDeclaredMethod("allocatePoints", Entity.class, PlayerVariables.class, int.class, int.class);
            allocation.setAccessible(true);
            int id = 2;
            double old = vars.attributePoints.getOrDefault("attribute_" + id, 0.0);
            int spent = (Integer)allocation.invoke(null, player, vars, id, 1);
            if (spent != 1 || vars.SparePoints != 2 || vars.attributePoints.getOrDefault("attribute_" + id, 0.0) != old + 1)
                throw new AssertionError("5.0.0 point-allocation logic failed");
            // Check player progression round trip in 5.0.0's own NBT codec.
            PlayerVariables restored = new PlayerVariables(); restored.readNBT(vars.writeNBT());
            if (restored.Level != 30 || restored.SparePoints != 2) throw new AssertionError("Progression NBT round trip failed");
            // Deserialize progression emitted by the actual installed 4.2.5 class, not a guessed schema.
            String variableClass = "tn.nightbeam.ras.network.PlayerVariables";
            byte[] legacyBytes;
            try (var jar = new java.util.jar.JarFile("../ras-upgrade/old-4.2.5.jar")) {
                legacyBytes = jar.getInputStream(jar.getJarEntry(variableClass.replace('.', '/') + ".class")).readAllBytes();
            }
            ClassLoader legacyLoader = new ClassLoader(RasUpgradeTest.class.getClassLoader()) {
                @Override protected Class<?> loadClass(String name, boolean resolve) throws ClassNotFoundException {
                    if (!name.equals(variableClass)) return super.loadClass(name, resolve);
                    Class<?> found = findLoadedClass(name);
                    if (found == null) found = defineClass(name, legacyBytes, 0, legacyBytes.length);
                    if (resolve) resolveClass(found);
                    return found;
                }
            };
            Class<?> oldType = legacyLoader.loadClass(variableClass);
            Object legacy = oldType.getConstructor().newInstance();
            oldType.getField("Level").setDouble(legacy, 17);
            oldType.getField("SparePoints").setDouble(legacy, 8);
            ((Map<String,Double>)oldType.getField("attributes").get(legacy)).put("attribute_2", 13.5);
            ((Map<String,Double>)oldType.getField("attributePoints").get(legacy)).put("attribute_2", 7.0);
            var tag = (net.minecraft.nbt.CompoundTag)oldType.getMethod("writeNBT").invoke(legacy);
            PlayerVariables migrated = new PlayerVariables(); migrated.readNBT(tag);
            if (migrated.Level != 17 || migrated.SparePoints != 8 || migrated.attributes.get("attribute_2") != 13.5
                    || migrated.attributePoints.get("attribute_2") != 7.0) throw new AssertionError("Legacy 4.2.5 player progress was not preserved");
            Class.forName("tn.nightbeam.ras.network.FabricAttributeAllocationPayload");
            System.out.println("HALFKNIFE RAS UPGRADE PASSED: real server, global levels 12/30, attribute-independent item locks, point allocation and progression NBT.");
        } catch (ReflectiveOperationException | java.io.IOException error) { throw new AssertionError(error); }
    }
}
