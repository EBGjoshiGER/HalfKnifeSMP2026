/* Derived from RPG Attribute System, Apache-2.0. HalfKnife server-only item-level patch. */
package tn.nightbeam.ras.events;

import net.fabricmc.fabric.api.entity.event.v1.ServerPlayerEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerEntityEvents;
import net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents;
import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.fabricmc.fabric.api.event.player.UseItemCallback;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.LivingEntity;

import tn.nightbeam.ras.platform.Services;
import tn.nightbeam.ras.network.PlayerVariables;
import tn.nightbeam.ras.procedures.OnPlayerSpawnProcedure;
import tn.nightbeam.ras.procedures.GiveXpCmdProcedure;
import tn.nightbeam.ras.procedures.GameplayRulesProcedure;
import tn.nightbeam.ras.procedures.LevelingService;
import tn.nightbeam.ras.RpgAttributeSystemMod;
import net.fabricmc.fabric.api.entity.event.v1.ServerEntityCombatEvents;

public class FabricRpgAttributeSystemModEvents {

    // HalfKnife: items use the overall RPG level; block locks remain a separate rule.
    private static boolean isItemLocked(ItemStack itemStack, Player player) {
        if (player == null || itemStack.isEmpty()) return false;
        if (!Services.CONFIG.getBooleanValue("ras", "items_lock", "enabled")) return false;
        String heldItemKey = BuiltInRegistries.ITEM.getKey(itemStack.getItem()).toString();
        for (String entry : Services.CONFIG.getArrayAsList("ras", "items_lock", "items_list")) {
            String itemKey = entry.substring(entry.indexOf("[item]") + 6, entry.indexOf("[itemEnd]"));
            if (!itemKey.equals(heldItemKey)) continue;
            double required;
            try { required = Double.parseDouble(entry.substring(entry.indexOf("[level]") + 7, entry.indexOf("[levelEnd]")).trim()); }
            catch (Exception ignored) { required = 0; }
            if (required > Services.PLATFORM.getPlayerVariables(player).Level) return true;
        }
        return false;
    }

    private static boolean shouldCancelBlockBreak(BlockState state, Player player) {
        return player != null && isItemLocked(player.getMainHandItem(), player);
    }

    public static void register() {
        ServerPlayerEvents.COPY_FROM.register((oldPlayer, newPlayer, alive) -> {
            PlayerVariables oldVars = Services.PLATFORM.getPlayerVariables(oldPlayer);
            PlayerVariables newVars = Services.PLATFORM.getPlayerVariables(newPlayer);
            newVars.readNBT(oldVars.writeNBT());
            OnPlayerSpawnProcedure.execute(newPlayer);
            Services.PLATFORM.syncPlayerVariables(newVars, newPlayer);
        });

        ServerPlayerEvents.AFTER_RESPAWN.register((oldPlayer, newPlayer, alive) -> {
            // Logic from WhenPlayerRespawnsProcedure
            if (Services.CONFIG.getBooleanValue("ras", "settings", "on_death_reset")) {
                LevelingService.resetProgress(newPlayer);
            }
            OnPlayerSpawnProcedure.execute(newPlayer);
            // Sync updated vars to client after respawn — the new player entity has a fresh
            // client-side attachment; without this the client shows default (Level 0) stats.
            Services.PLATFORM.syncPlayerVariables(Services.PLATFORM.getPlayerVariables(newPlayer), newPlayer);
        });

        net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents.JOIN.register((handler, sender, server) -> {
            Services.PLATFORM.syncAttributeConfig(handler.getPlayer());
            Services.PLATFORM.syncItemsLockConfig(handler.getPlayer());
            Services.PLATFORM.syncItemsLockConfig(handler.getPlayer());
            Services.PLATFORM.syncStatsDisplayConfig(handler.getPlayer());
            OnPlayerSpawnProcedure.execute(handler.getPlayer());
            Services.PLATFORM.syncPlayerVariables(Services.PLATFORM.getPlayerVariables(handler.getPlayer()),
                    handler.getPlayer());
        });

        net.fabricmc.fabric.api.entity.event.v1.ServerEntityLevelChangeEvents.AFTER_PLAYER_CHANGE_LEVEL.register(
                (player, origin, destination) -> {
                    OnPlayerSpawnProcedure.execute(player);
                    Services.PLATFORM.syncPlayerVariables(Services.PLATFORM.getPlayerVariables(player), player);
                });

        ServerEntityCombatEvents.AFTER_KILLED_OTHER_ENTITY.register((world, entity, killedEntity, damageSource) -> {
            GameplayRulesProcedure.handleEntityKill(world, entity, killedEntity);
        });

        PlayerBlockBreakEvents.BEFORE.register((world, player, pos, state, blockEntity) -> {
            if (shouldCancelBlockBreak(state, player) || GameplayRulesProcedure.shouldCancelBlockBreak(state, player)) {
                if (!world.isClientSide()) {
                    GameplayRulesProcedure.sendBlockRequirementMessage(state, player);
                }
                return false;
            }
            return true;
        });

        // Attack Entity Event (Left Click)
        AttackEntityCallback.EVENT.register((player, world, hand, entity, hitResult) -> {
            if (!world.isClientSide() && isItemLocked(player.getItemInHand(hand), player)) {
                player.sendSystemMessage(Component.literal("\u00A74You can't use this item yet"));
                return InteractionResult.FAIL;
            }
            return InteractionResult.PASS;
        });

        // Use Item Event (Right Click)
        UseItemCallback.EVENT.register((player, world, hand) -> {
            if (!world.isClientSide() && isItemLocked(player.getItemInHand(hand), player)) {
                player.sendSystemMessage(Component.literal("\u00A74You can't use this item yet"));
                return InteractionResult.FAIL;
            }
            return InteractionResult.PASS;
        });
        // Preserve the previous server's equipment enforcement and item return behavior.
        ServerEntityEvents.EQUIPMENT_CHANGE.register((livingEntity, slot, previousStack, currentStack) -> {
            if (!(livingEntity instanceof Player player) || currentStack.isEmpty() || !isItemLocked(currentStack, player)) return;
            ItemStack lockedStack = currentStack.copy();
            player.setItemSlot(slot, ItemStack.EMPTY);
            if (!player.getInventory().add(lockedStack)) player.drop(lockedStack, false);
            player.sendSystemMessage(Component.literal("\u00a74You need a higher level to equip this item"));
        });
    }
}
