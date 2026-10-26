package de.halfknife.netherproject;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.SimpleMenuProvider;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ChestMenu;
import net.minecraft.world.item.ItemStack;

public final class ProjectGui {
    private ProjectGui() {}

    public static void open(ServerPlayer player) {
        if (NetherProjectMod.STATE.completed) {
            player.sendSystemMessage(Component.literal("§aDas Nether-Projekt ist bereits abgeschlossen."));
            NetherProjectMod.sendStatus(player);
            return;
        }
        if (!NetherProjectMod.STATE.active) {
            player.sendSystemMessage(Component.literal("§7Das Nether-Projekt wurde noch nicht gestartet."));
            return;
        }
        if (NetherProjectMod.STATE.paused) {
            player.sendSystemMessage(Component.literal("§eDas Nether-Projekt ist momentan pausiert."));
            return;
        }

        SimpleContainer deposit = new SimpleContainer(54);
        player.openMenu(new SimpleMenuProvider((containerId, playerInventory, ignored) ->
                new ChestMenu(net.minecraft.world.inventory.MenuType.GENERIC_9x6, containerId, playerInventory, deposit, 6) {
                    private boolean processed = false;

                    @Override
                    public void removed(Player closingPlayer) {
                        if (!processed && closingPlayer instanceof ServerPlayer serverPlayer) {
                            processed = true;
                            processDeposit(serverPlayer, deposit);
                        }
                        super.removed(closingPlayer);
                    }
                }, Component.literal(NetherProjectMod.CONFIG.guiTitle)));
    }

    private static void processDeposit(ServerPlayer player, SimpleContainer deposit) {
        int acceptedTotal = 0;
        int pointsTotal = 0;

        for (int slot = 0; slot < deposit.getContainerSize(); slot++) {
            ItemStack stack = deposit.getItem(slot);
            if (stack.isEmpty()) continue;

            ItemStack original = stack.copy();
            String itemId = BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
            ProjectState.DonationResult result = NetherProjectMod.STATE.donate(player, itemId, stack.getCount(), NetherProjectMod.CONFIG);
            acceptedTotal += result.items();
            pointsTotal += result.points();

            deposit.setItem(slot, ItemStack.EMPTY);
            int remainder = original.getCount() - result.items();
            if (remainder > 0) {
                ItemStack returnStack = original.copy();
                returnStack.setCount(remainder);
                giveBack(player, returnStack);
            }
        }

        if (acceptedTotal > 0) {
            player.sendSystemMessage(Component.literal("§a+" + acceptedTotal + " Items §7(§e" + pointsTotal + " Punkte§7) §azum Nether-Projekt beigetragen."));
            if (NetherProjectMod.CONFIG.broadcastDonations) NetherProjectMod.broadcastDonation(player, acceptedTotal, pointsTotal);
        } else {
            player.sendSystemMessage(Component.literal("§7Keine benötigten Items eingezahlt."));
        }

        NetherProjectMod.afterProgressChanged();
        NetherProjectMod.sendStatus(player);
    }

    private static void giveBack(ServerPlayer player, ItemStack stack) {
        if (!player.getInventory().add(stack)) player.spawnAtLocation(player.level(), stack);
    }
}
