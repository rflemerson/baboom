The Scrapy project owns request scheduling and transport policy, not payload extraction or store configuration; robots.txt remains disabled because the previous crawler did not obey it and enabling it is a product decision.

The Celery monitor enforces a 30-minute wall-clock limit on its child process.
An unrelated `ERROR` log is diagnostic, not a failed crawl; exit status and
Scrapy's close reason determine whether the run failed.
