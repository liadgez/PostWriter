#!/usr/bin/env python3
"""Setup script for social-content-generator."""

from setuptools import setup, find_packages

with open("Readme.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="social-content-generator",
    version="1.0.0",
    author="Liad Gez",
    description="Facebook post analyzer and content generator for marketing automation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/liadgez/social-content-generator",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Communications :: Chat",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Text Processing :: Linguistic",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "postwriter=postwriter:main",
            "quick-scrape=quick_scrape:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="facebook, social-media, content-generation, marketing, automation, scraping",
)