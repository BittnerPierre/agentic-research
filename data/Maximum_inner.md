---
title: "Maximum inner"
source: "https://en.wikipedia.org/wiki/Maximum_inner_product_search"
content_length: 5259
---

# Maximum inner

**Source:** [https://en.wikipedia.org/wiki/Maximum_inner_product_search](https://en.wikipedia.org/wiki/Maximum_inner_product_search)

## Contenu

From Wikipedia, the free encyclopedia
(Redirected from [Maximum inner product search](</w/index.php?title=Maximum_inner_product_search&redirect=no> "Maximum inner product search"))
Search problem
**Maximum inner-product search** (**MIPS**) is a [search problem](</wiki/Search_problem> "Search problem"), with a corresponding class of [search algorithms](</wiki/Search_algorithm> "Search algorithm") which attempt to maximise the [inner product](</wiki/Inner_product_space> "Inner product space") between a query and the data items to be retrieved. MIPS algorithms are used in a wide variety of big data applications, including [recommendation algorithms](</wiki/Recommendation_algorithm> "Recommendation algorithm") and [machine learning](</wiki/Machine_learning> "Machine learning").[1]
Formally, for a database of vectors  x i {\displaystyle x_{i}} defined over a set of labels  S {\displaystyle S} in an [inner product space](</wiki/Inner_product_space> "Inner product space") with an inner product  ⟨ ⋅ , ⋅ ⟩ {\displaystyle \langle \cdot ,\cdot \rangle } defined on it, MIPS search can be defined as the problem of determining
a r g m a x i ∈ S ⟨ x i , q ⟩ {\displaystyle {\underset {i\in S}{\operatorname {arg\,max} }}\ \langle x_{i},q\rangle }
for a given query  q {\displaystyle q} .
Although there is an obvious [linear-time](</wiki/Linear-time> "Linear-time") implementation, it is generally too slow to be used on practical problems. However, efficient algorithms exist to speed up MIPS search.[1][2]
Under the assumption of all vectors in the set having constant norm, MIPS can be viewed as equivalent to a [nearest neighbor search](</wiki/Nearest_neighbor_search> "Nearest neighbor search") (NNS) problem in which maximizing the inner product is equivalent to minimizing the corresponding [distance metric](</wiki/Distance_metric> "Distance metric") in the NNS problem.[3] Like other forms of NNS, MIPS algorithms may be approximate or exact.[4]
MIPS search is used as part of [DeepMind](</wiki/DeepMind> "DeepMind")'s [RETRO](</w/index.php?title=RETRO_\(algorithm\)&action=edit&redlink=1> "RETRO \(algorithm\) \(page does not exist\)") algorithm.[5]
## References
[[edit](</w/index.php?title=Maximum_inner-product_search&action=edit&section=1> "Edit section: References")]
1. ^ _
* a
* b
* _ Abuzaid, Firas; Sethi, Geet; Bailis, Peter; Zaharia, Matei (2019-03-14). "To Index or Not to Index: Optimizing Exact Maximum Inner Product Search". [arXiv](</wiki/ArXiv_\(identifier\)> "ArXiv \(identifier\)"):[1706.01449](<https://arxiv.org/abs/1706.01449>) [[cs.IR](<https://arxiv.org/archive/cs.IR>)].
2.
* ^
* Steve Mussmann, Stefano Ermon. Learning and Inference via Maximum Inner Product Search. In _Proc. 33rd International Conference on Machine Learning_ (ICML), 2016.
3.
* ^
* Shrivastava, Anshumali; Li, Ping (2015-07-12). ["Improved asymmetric locality sensitive hashing (ALSH) for Maximum Inner Product Search (MIPS)"](<https://dl.acm.org/doi/abs/10.5555/3020847.3020931>). _Proceedings of the Thirty-First Conference on Uncertainty in Artificial Intelligence_. UAI'15. Arlington, Virginia, USA: AUAI Press: 812–821\. [arXiv](</wiki/ArXiv_\(identifier\)> "ArXiv \(identifier\)"):[1410.5410](<https://arxiv.org/abs/1410.5410>). [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-0-9966431-0-8](</wiki/Special:BookSources/978-0-9966431-0-8> "Special:BookSources/978-0-9966431-0-8").
4.
* ^
* Keivani, Omid; Sinha, Kaushik; Ram, Parikshit (May 2017). "Improved maximum inner product search with better theoretical guarantees". _2017 International Joint Conference on Neural Networks (IJCNN)_. pp. 2927–2934\. [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1109/IJCNN.2017.7966218](<https://doi.org/10.1109%2FIJCNN.2017.7966218>). [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-1-5090-6182-2](</wiki/Special:BookSources/978-1-5090-6182-2> "Special:BookSources/978-1-5090-6182-2"). [S2CID](</wiki/S2CID_\(identifier\)> "S2CID \(identifier\)") [8352165](<https://api.semanticscholar.org/CorpusID:8352165>).
5.
* ^
* ["RETRO Is Blazingly Fast"](<http://mitchgordon.me/ml/2022/07/01/retro-is-blazing.html>). _Mitchell A. Gordon_. 2022-07-01. Retrieved 2022-07-04.
## See also
[[edit](</w/index.php?title=Maximum_inner-product_search&action=edit&section=2> "Edit section: See also")]
* [Nearest neighbor search](</wiki/Nearest_neighbor_search> "Nearest neighbor search")
Retrieved from "[https://en.wikipedia.org/w/index.php?title=Maximum_inner-product_search&oldid=1303325176](<https://en.wikipedia.org/w/index.php?title=Maximum_inner-product_search&oldid=1303325176>)"
[Categories](</wiki/Help:Category> "Help:Category"):
* [Search algorithms](</wiki/Category:Search_algorithms> "Category:Search algorithms")
* [Computational problems](</wiki/Category:Computational_problems> "Category:Computational problems")
* [Machine learning](</wiki/Category:Machine_learning> "Category:Machine learning")
Hidden categories:
* [Articles with short description](</wiki/Category:Articles_with_short_description> "Category:Articles with short description")
* [Short description is different from Wikidata](</wiki/Category:Short_description_is_different_from_Wikidata> "Category:Short description is different from Wikidata")

---
*Document traité automatiquement par le système de recherche agentique*
