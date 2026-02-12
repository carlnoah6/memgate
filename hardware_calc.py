def calc_training(params_b, tokens_b, gpu_name, tflops_eff):
    total_flops = 6 * (params_b * 1e9) * (tokens_b * 1e9)
    flops_per_sec = tflops_eff * 1e12
    seconds = total_flops / flops_per_sec
    hours = seconds / 3600
    days = hours / 24
    return f"{gpu_name}: {days:.1f} days ({hours:.0f} hours)"

print("Training 1B Model on 100B Tokens (Small-scale pre-training):")
print(calc_training(1, 100, "1x RTX 4090 (Est 50 TFLOPS eff)", 50))
print(calc_training(1, 100, "1x A100 80GB (Est 150 TFLOPS eff)", 150))
print(calc_training(1, 100, "1x H100 (Est 350 TFLOPS eff)", 350))
print(calc_training(1, 100, "8x A100 (Cluster)", 150 * 8))
print(calc_training(1, 100, "8x H100 (Cluster)", 350 * 8))
