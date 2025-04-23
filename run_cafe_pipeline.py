#!/usr/bin/env python
import asyncio
import sys
from cafe_data_collection.run_pipeline import main

if __name__ == "__main__":
    # Run the pipeline
    asyncio.run(main()) 