import polars as pl, glob, sys
RAW="../data/raw/c0b3a9190fd970e83cfbe7d399a08860e43e221e/data"
dfs={s: pl.read_parquet(sorted(glob.glob(f"{RAW}/{s}-*.parquet"))) for s in ["train","dev","test"]}
tot=0
for s,df in dfs.items():
    qn=df["questions_count"].sum(); tot+=qn
    print(s, "rows", df.height, "questions_count sum", qn, "len(questions) sum", df["questions"].list.len().sum(),
          "rows with 0 q", (df["questions_count"]==0).sum(), "unique path", df["path"].n_unique(), "unique email", df["email"].n_unique(), "users", df["user"].n_unique())
print("TOTAL questions", tot)
print(dfs["train"].schema)
# cross-split overlap of path
p={s:set(df["path"].to_list()) for s,df in dfs.items()}
print("path overlap train&dev", len(p["train"]&p["dev"]), "train&test", len(p["train"]&p["test"]), "all3", len(p["train"]&p["dev"]&p["test"]), "union", len(p["train"]|p["dev"]|p["test"]))
# emails with >0 questions in any split
nz={s:set(df.filter(pl.col("questions_count")>0)["path"].to_list()) for s,df in dfs.items()}
print("paths with >=1 question union", len(nz["train"]|nz["dev"]|nz["test"]))
# lengths consistency
df=dfs["train"]
for c in ["questions","rephrased_questions","gold_answers","alternate_answers","incorrect_answers","gold_rationales","alternate_rationales","include_email"]:
    print(c, "len==questions_count all?", (df[c].list.len()==df["questions_count"]).all())
r=dfs["dev"].filter(pl.col("questions_count")>=2).row(0,named=True)
import json
for k,v in r.items():
    if k=="email": print("EMAIL:", v[:1500]); continue
    print(k, json.dumps(v,ensure_ascii=False)[:900])
