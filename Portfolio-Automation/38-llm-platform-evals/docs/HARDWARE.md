# Hardware Specification — Homelab Execution Environment

Specifications of the homelab machine hosting the System Under Test (SUT) and eval executions:

| Component | Specification | Details / Command Evidence |
|---|---|---|
| **Host / OS** | Debian GNU/Linux 13 (trixie/sid) | Kernel `6.12.90+deb13.1-amd64 #1 SMP PREEMPT_DYNAMIC` |
| **CPU** | Intel(R) Core(TM) i5-8300H CPU @ 2.30GHz | 4 physical cores, 8 threads (vCPUs), 64-bit Little Endian, max 4.00GHz |
| **RAM** | 7.6 GiB Total (~8 GB DDR4) | Available: ~5.5 GiB, Swap: 7.9 GiB total (670 MiB used) |
| **GPU** | NVIDIA GeForce GTX 1050 Mobile | 4096 MiB VRAM (Driver: 550.163.01, CUDA 12.4) |
| **Storage** | NVMe SSD | Host filesystem ext4 |
| **Network** | Gigabit Ethernet (1000BASE-T) | Static homelab IP `192.168.1.15` |
| **Local LLM Engine** | Ollama (systemd service) | Binding `127.0.0.1:11434`, serving `qwen3:4b-instruct-2507-q4_K_M` |
