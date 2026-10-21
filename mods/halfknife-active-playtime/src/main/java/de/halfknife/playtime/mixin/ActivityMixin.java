package de.halfknife.playtime.mixin;

import de.halfknife.playtime.ActivePlaytimeMod;
import net.minecraft.network.protocol.game.ServerboundMovePlayerPacket;
import net.minecraft.network.protocol.game.ServerboundPlayerInputPacket;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ServerGamePacketListenerImpl.class)
public abstract class ActivityMixin {
    @Unique private float halfknife$yaw = Float.NaN;
    @Unique private float halfknife$pitch = Float.NaN;

    @Inject(method = "handlePlayerInput", at = @At("TAIL"))
    private void halfknife$input(ServerboundPlayerInputPacket packet, CallbackInfo ci) {
        var input = packet.input();
        boolean moving = input.forward() || input.backward() || input.left() || input.right() || input.jump();
        ActivePlaytimeMod.input(((ServerGamePacketListenerImpl)(Object)this).player, moving);
    }

    @Inject(method = "handleMovePlayer", at = @At("TAIL"))
    private void halfknife$look(ServerboundMovePlayerPacket packet, CallbackInfo ci) {
        if (!packet.hasRotation()) return;
        float yaw = packet.getYRot(0);
        float pitch = packet.getXRot(0);
        if (Float.isFinite(yaw) && Float.isFinite(pitch) && (yaw != halfknife$yaw || pitch != halfknife$pitch)) {
            halfknife$yaw = yaw;
            halfknife$pitch = pitch;
            ActivePlaytimeMod.activity(((ServerGamePacketListenerImpl)(Object)this).player);
        }
    }

    @Inject(method = {"handlePlayerAction", "handleSetCarriedItem", "handleContainerClick", "handleChat"}, at = @At("TAIL"))
    private void halfknife$action(CallbackInfo ci) {
        ActivePlaytimeMod.activity(((ServerGamePacketListenerImpl)(Object)this).player);
    }
}
