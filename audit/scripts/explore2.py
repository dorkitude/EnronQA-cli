import polars as pl, glob, re, collections
RAW="../data/raw/c0b3a9190fd970e83cfbe7d399a08860e43e221e/data"
dfs={s: pl.read_parquet(sorted(glob.glob(f"{RAW}/{s}-*.parquet"))) for s in ["train","dev","test"]}
# email identity across splits
j=dfs["train"].select("path",e1="email").join(dfs["dev"].select("path",e2="email"),on="path").join(dfs["test"].select("path",e3="email"),on="path")
print("email identical train/dev/test:", (j["e1"]==j["e2"]).all(), (j["e1"]==j["e3"]).all())
# users overlap
print("user sets equal:", set(dfs["train"]["user"])==set(dfs["test"]["user"]))
for s,df in dfs.items():
    q=df.select(pl.col("questions").list.len().alias("n"), "include_email","gold_answers","alternate_answers","incorrect_answers","questions")
    inc=df.explode("include_email")["include_email"].value_counts().sort("include_email")
    print(s,"include_email dist", inc.to_dicts())
    ex=df.select("questions","gold_answers","alternate_answers","incorrect_answers").explode(["questions","gold_answers","alternate_answers","incorrect_answers"])
    print(s,"gold len words: mean %.1f median %d p90 %d max %d"%(ex["gold_answers"].str.split(" ").list.len().mean(), ex["gold_answers"].str.split(" ").list.len().median(), ex["gold_answers"].str.split(" ").list.len().quantile(0.9), ex["gold_answers"].str.split(" ").list.len().max()))
    print(s,"n alt answers dist", ex["alternate_answers"].list.len().value_counts().sort("alternate_answers").to_dicts()[:6])
    print(s,"n incorrect dist", ex["incorrect_answers"].list.len().value_counts().sort("incorrect_answers").to_dicts()[:6])
    fw=collections.Counter(q.split()[0].lower().strip('",') if q.split() else "" for q in ex["questions"].to_list())
    print(s,"first word", fw.most_common(15))
    print(s,"dup questions within split", ex.height-ex["questions"].n_unique())
ex=dfs["test"].select("path","questions","gold_answers").explode(["questions","gold_answers"])
import random; random.seed(1)
for r in random.sample(ex.to_dicts(),12): print("Q:",r["questions"],"\n   A:",r["gold_answers"])
