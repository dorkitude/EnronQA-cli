# Dataset licensing

The CLI code is MIT licensed. That license does not cover the EnronQA dataset
or the underlying Enron emails. Neither is bundled with this repository or its
release packages; `enronqa fetch` downloads data from the upstream host.

## Upstream sources

- [EnronQA dataset](https://huggingface.co/datasets/MichaelR207/enron_qa_0922),
  pinned to revision `c0b3a9190fd970e83cfbe7d399a08860e43e221e`:
  the dataset card at this revision does not declare a license, and the
  repository contains no LICENSE file.
- [EnronQA paper](https://arxiv.org/abs/2505.00263): released under CC BY 4.0.
  The paper's license does not establish a license for the dataset.
- [CMU Enron corpus](https://www.cs.cmu.edu/~enron/): the distribution page
  describes research use and requests respect for the individuals' privacy;
  it does not specify a formal copyright license. Some messages were removed
  following requests from affected employees.

Public availability does not establish public-domain status. EnronQA includes
email text and generated questions and answers that can reproduce information
from those emails. Consult the upstream terms before redistributing dataset
content.
