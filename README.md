# Bogged Again!

<!-- TODO: Enable logo to be retrieved from aws s3 by adjusting permissions -->
![Bogged Again! Logo](/media/images/bogheader.png)

[Bogged Again!](http://www.boggedaga.in/) is a python-based service that provides quantitative insight into the adage, "Buy low, sell high".

Given a ticker that is currently in the red, Bogged Again! searches through the last two years of available financial data for dates when the stock had a greater percentage drop. The corresponding percentage change three days later is displayed (corresponds to Fidelity's trade settling period).

Bogged Again! will skip analysis of a given ticker if the stock was in the positive today or if similar movement has been observed at least 100 times over the last two years (roughly 500 business days).

[The Bogchives](http://www.boggedaga.in/bogchives/) is an archive of the past stock records.


## Prerequisites

- AWS CLI version 1
- git
- Python 3.6 (for compatibility with tensorflow)


## Installation

Clone the repo (Unix or MacOS) with
```
$ git clone https://github.com/deekew33/bogged-again.git
```

<!-- TODO: Figure out the git/s3 workflow. Maybe look at the following links: -->
<!-- https://stackoverflow.com/questions/7031729/publish-to-s3-using-git -->
<!-- https://medium.com/@sithum/automate-static-website-deployment-from-github-to-s3-using-aws-codepipeline-16acca25ebc1 -->
Contact @deekew33 for access to additional files on Amazon S3. The most up-to-date files can be retrieved through
```
$ cd bogged-again
$ aws s3 sync s3://boggedagain/ .
```

Additionally, `google_api_certs.env` must be added under `polls/boggedagain`, where the first line contains the custom search engine ID and the second line contains the API key. Once all files are present in the root `bogged-again` directory, create a virtual environment (Python 3.6) in a sibling directory:
```bash
$ python -m venv ../bogged-again-env
```

Then, activate the virtual environment and install the necessary packages. On Unix or MacOS, run:
```bash
$ source ../bogged-again-env/bin/activate
(bogged-again-env) $ pip install -r requirements.txt
```

On Windows, run:
```
> ..\bogged-again-env\Scripts\activate.bat
(bogged-again-env) > pip install -r requirements.txt
```

To exit the virtual environment, simply run `deactivate`.


## Getting started

While in the root `bogged-again` directory, start a development server with:
```bash
$ python manage.py runserver
```

