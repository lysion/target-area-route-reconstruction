# F6 benchmark protocol v5 — rejected trial

This is a retained failed calibration trial, not acceptance evidence. The
protocol used the same fixed batch for baseline and candidate at each size, but
the 800-part producer candidate's fastest measured batch was 17.556 ms, below
the declared 20 ms timer floor. The trial therefore failed before producing a
three-clean-run report. Its predeclared batches were 200/128/32/16 for
200/400/800/1600 parts. Protocol v6 increases them to 200/128/64/32 and reruns
all three clean processes. No timing from v5 is counted as a pass.
