data_921a_15 = from(bucket: "SnowRanger")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "distance")
  |> filter(fn: (r) => r["_field"] == "distance")
  |> filter(fn: (r) => r["from"] == "921a_15")
  |> map(fn: (r) => ({ r with _value: 1035.0 - r._value }))

data_921a_18 = from(bucket: "SnowRanger")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "distance")
  |> filter(fn: (r) => r["_field"] == "distance")
  |> filter(fn: (r) => r["from"] == "921a_18")
  |> map(fn: (r) => ({ r with _value: 1220.0 - r._value }))

union(tables: [data_921a_15, data_921a_18])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")