"""GPU sanity check: torch/CUDA versions, device, small matmul vs CPU, villa infer import."""
import json, sys, time, os
import torch
r = {"python": sys.version.split()[0], "torch": torch.__version__, "torch_cuda": torch.version.cuda,
     "cudnn": torch.backends.cudnn.version(), "cuda_available": torch.cuda.is_available()}
if r["cuda_available"]:
    p = torch.cuda.get_device_properties(0)
    r.update(device_name=torch.cuda.get_device_name(0), capability=list(torch.cuda.get_device_capability(0)),
             total_mem_mib=p.total_memory // 2**20, arch_list=torch.cuda.get_arch_list())
    g = torch.Generator().manual_seed(0)
    a = torch.randn(2048, 2048, generator=g); b = torch.randn(2048, 2048, generator=g)
    ref = a @ b
    torch.cuda.synchronize(); t = time.time()
    c = (a.cuda() @ b.cuda()); torch.cuda.synchronize()
    r["matmul_2048_fp32_s"] = round(time.time() - t, 4)
    r["matmul_max_abs_err_vs_cpu"] = float((c.cpu() - ref).abs().max())
    r["matmul_rel_err"] = float((c.cpu() - ref).norm() / ref.norm())
    with torch.autocast("cuda", dtype=torch.bfloat16):
        cb = a.cuda() @ b.cuda()
    r["matmul_bf16_rel_err"] = float((cb.float().cpu() - ref).norm() / ref.norm())
    r["mem_free_mib"], _ = [x // 2**20 for x in torch.cuda.mem_get_info()]
sys.path.insert(0, sys.argv[1])
import vesuvius.ink_detection.inference.infer as infer  # noqa: F401
r["villa_infer_import"] = "ok"
print(json.dumps(r, indent=1))
