| Run | Learning Rate | Gamma | Replay Buffer Size | Batch Size | Exploration Strategy | Target Update | Network | Mean Reward (points) | Win rate | Mean cost (bps) | Forced-sale rate | Invalid actions per game |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dqn_01 | 0.0001 | 0.995 | 100000 | 128 | epsilon-greedy 1.0 to 0.05 over 150,000 frames | soft, tau 0.005 | 2 x 128 | -25.00 | 5.2% | 184.7 | 93.8% | 0.25 |
| dqn_02 | 0.0003 | 0.995 | 100000 | 128 | epsilon-greedy 1.0 to 0.05 over 150,000 frames | soft, tau 0.005 | 2 x 128 | -30.17 | 10.4% | 172.9 | 80.0% | 7.34 |
| dqn_03 | 0.0005 | 0.995 | 100000 | 128 | epsilon-greedy 1.0 to 0.05 over 150,000 frames | soft, tau 0.005 | 2 x 128 | -23.49 | 11.4% | 180.6 | 73.4% | 0.02 |
| dqn_04 | 0.001 | 0.995 | 100000 | 128 | epsilon-greedy 1.0 to 0.05 over 150,000 frames | soft, tau 0.005 | 2 x 128 | -45.19 | 9.4% | 186.3 | 88.4% | 20.87 |
| dqn_05 | 0.003 | 0.995 | 100000 | 256 | epsilon-greedy 1.0 to 0.05 over 150,000 frames | soft, tau 0.005 | 2 x 128 | -43.59 | 13.0% | 175.6 | 85.6% | 20.85 |
| dqn_06 | 0.0005 | 0.995 | 20000 | 64 | epsilon-greedy 1.0 to 0.05 over 150,000 frames | soft, tau 0.005 | 2 x 128 | -26.29 | 5.6% | 172.0 | 94.4% | 2.87 |
| dqn_07 | 0.0005 | 0.995 | 300000 | 256 | epsilon-greedy 1.0 to 0.05 over 150,000 frames | soft, tau 0.005 | 2 x 128 | -36.98 | 7.4% | 182.3 | 91.8% | 12.79 |
| dqn_08 | 0.0005 | 0.995 | 100000 | 128 | epsilon-greedy 1.0 to 0.01 over 400,000 frames | soft, tau 0.005 | 2 x 128 | -24.55 | 12.2% | 173.0 | 84.0% | 1.96 |
| dqn_09 | 0.0005 | 0.995 | 100000 | 128 | epsilon-greedy 1.0 to 0.05 over 150,000 frames | hard, every 1000 updates | 2 x 128 | -24.53 | 9.0% | 183.0 | 88.2% | 0.49 |
| dqn_10 | 0.0005 | 0.99 | 100000 | 128 | epsilon-greedy 1.0 to 0.1 over 50,000 frames | soft, tau 0.02 | 2 x 256 | -24.37 | 6.8% | 180.9 | 86.2% | 0.23 |
