#!/usr/bin/env python
import asyncio

from articles.article import ArticlePipeline


async def main():
    # Initialize the pipeline with an input file
    pipeline = ArticlePipeline("articles/input/input.json")
    # Run the pipeline
    await pipeline.run_pipeline()


if __name__ == "__main__":
    asyncio.run(main())
