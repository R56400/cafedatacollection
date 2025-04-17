from setuptools import setup, find_packages

# Read version from __init__.py
with open('cafe_data_collection/__init__.py', 'r') as f:
    for line in f:
        if line.startswith('__version__'):
            version = line.split('=')[1].strip().strip('"').strip("'")
            break

# Read README for long description
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='cafe_data_collection',
    version=version,
    description='A system to collect and process cafe data using LLMs',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Chris Jordan',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/cafe-data-collection',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'httpx>=0.27.0',
        'pandas>=2.2.1',
        'pydantic>=2.6.3',
        'tqdm>=4.66.2',
        'python-dotenv>=1.0.1',
        'openpyxl>=3.1.2',
        'python-slugify>=8.0.4'
    ],
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    entry_points={
        'console_scripts': [
            'cafe-collector=cafe_data_collection.main:main',
        ],
    }
) 