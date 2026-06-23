# Configuration templates

## `epibench setup`

```yaml
---

hub: "" # must be one of 'flusight', 'flu metrocast', 'rsv', 'covid19'

dates: {
    start_date: YYYY-MM-DD, # dates are inclusive on both ends [,]
    end_date: YYYY-MM-DD,
    freq: "n weeks" # format must be: "<num> week" or "<num> weeks"
} 
# or, just a list of dates
# e.g.,
# dates: [YYYY-MM-DD, YYYY-MM-DD, YYYY-MM-DD]

vintaging: TRUE

output_path: "/..."
```

## `epibench score`

```yaml
---

hub: "" # must be one of 'flusight', 'flu metrocast', 'rsv', 'covid19'

evaluation_start_date: "YYYY-MM-DD" 
evaluation_end_date: "YYYY-MM-DD" # dates are inclusive on both ends [,]

target: "wk inc flu hosp" # only scores one target at a time; match must be exact

models: {
    "name-of-model1": "/path/to/model1-data", # paths can point to a folder of CSVs
    "name-of-model2": "/path/to/model2-data", # or to a single CSV
    "name-of-model3": "/path/to/model3-data"
} 
# non-quantile output will be filtered out

output_path: "/..."
```

## `epibench plot`

coming soon