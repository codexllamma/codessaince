import sys
import paddle

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

print("--- PADDLEPADDLE GPU DIAGNOSTIC ---")
print(f"Paddle Version: {paddle.__version__}")
print(f"Is compiled with CUDA: {paddle.device.is_compiled_with_cuda()}")

if paddle.device.is_compiled_with_cuda():
    print(f"Currently Active Device: {paddle.device.get_device()}")
    print("✅ Your GPU is recognized and ready!")
else:
    print("❌ GPU NOT DETECTED. PaddlePaddle is using the CPU.")