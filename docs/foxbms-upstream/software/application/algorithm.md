# Algorithm Module (State Estimation)

**Source**: [docs.foxbms.org — Algorithm](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/application/algorithm/algorithm.html)
**Files**: `src/app/application/algorithm/`
**Status**: Upstream documentation marked "not yet complete"

---

## Included Algorithms

- **SOC** (State of Charge) — coulomb counting method
- **SOE** (State of Energy) — energy remaining estimate
- **SOF** (State of Function) — power capability estimate

## SOC: Coulomb Counting

```
SOC(t) = SOC(t-1) - (I × dt) / (Capacity × 3600)
```

- Runs in 100ms Algorithm task (`FTSK_RunUserCodeCyclicAlgorithm100ms`)
- Reported on CAN 0x235
- Drifts over time without correction (no EKF/LSTM in production foxBMS)

## POSIX Port Status

- SOC works dynamically with plant model current (10A discharge → SOC decreases)
- SOE/SOF run but use static voltage/temperature values
- This is where ML integration adds value: SOC LSTM (1.83% RMSE) vs coulomb counting (5-10% drift)
