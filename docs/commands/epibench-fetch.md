# `epibench fetch`

Running `epibench fetch <challenge-id> --output-path ".../..."` via the command line downloads the bundled challenge to the directory specified by `--output-path`. After a successful run, you will find the following:

* a directory titled <`challenge-id`>
    * `agent.md`: a file to inform an agent where to find instructions associated with the challenge
    * `instruction.md`: a file with a description of how to properly utilize the fetched data for forecasting, including the columns your model output should contain
    * `<challenge-id>.json`: the JSON file that internally defines the challenge
    *  `task_list.csv`: a CSV file with two columns; the reference date and the corresponding relative path to the ground truth vintaged to that date
    * `gt/`: a folder that contains the ground truth data
        * each ground truth data file is nested in `gt/YYYY-MM-DD/YYYYMMDD_gt.parquet`, where `YYYY-MM-DD` is a given reference date

## example usage:

```bash
epibench fetch epb_flu_inchosp_2024-2025_dev --output-path "/Users/user/Desktop"
```
