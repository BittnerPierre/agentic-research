---
title: "Nearest neighbor search"
source: "https://en.wikipedia.org/wiki/Approximate_nearest_neighbor_search"
content_length: 40493
---

# Nearest neighbor search

**Source:** [https://en.wikipedia.org/wiki/Approximate_nearest_neighbor_search](https://en.wikipedia.org/wiki/Approximate_nearest_neighbor_search)

## Contenu

From Wikipedia, the free encyclopedia
(Redirected from [Approximate nearest neighbor search](</w/index.php?title=Approximate_nearest_neighbor_search&redirect=no> "Approximate nearest neighbor search"))
Optimization problem in computer science
**Nearest neighbor search** (**NNS**), as a form of **proximity search** , is the [optimization problem](</wiki/Optimization_problem> "Optimization problem") of finding the point in a given set that is closest (or most similar) to a given point. Closeness is typically expressed in terms of a dissimilarity function: the less [similar](</wiki/Similarity_measure> "Similarity measure") the objects, the larger the function values.
Formally, the nearest-neighbor (NN) search problem is defined as follows: given a set _S_ of points in a space _M_ and a query point _q_ ∈  _M_ , find the closest point in _S_ to _q_. [Donald Knuth](</wiki/Donald_Knuth> "Donald Knuth") in vol. 3 of _[The Art of Computer Programming](</wiki/The_Art_of_Computer_Programming> "The Art of Computer Programming")_ (1973) called it the
* post-office problem
* , referring to an application of assigning to a residence the nearest post office. A direct generalization of this problem is a _k_ -NN search, where we need to find the _k_ closest points.
Most commonly _M_ is a [metric space](</wiki/Metric_space> "Metric space") and dissimilarity is expressed as a [distance metric](</wiki/Distance_metric> "Distance metric"), which is symmetric and satisfies the [triangle inequality](</wiki/Triangle_inequality> "Triangle inequality"). Even more common, _M_ is taken to be the _d_ -dimensional [vector space](</wiki/Vector_space> "Vector space") where dissimilarity is measured using the [Euclidean distance](</wiki/Euclidean_distance> "Euclidean distance"), [Manhattan distance](</wiki/Taxicab_geometry> "Taxicab geometry") or other [distance metric](</wiki/Statistical_distance> "Statistical distance"). However, the dissimilarity function can be arbitrary. One example is asymmetric [Bregman divergence](</wiki/Bregman_divergence> "Bregman divergence"), for which the triangle inequality does not hold.[1]
## Applications
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=1> "Edit section: Applications")]
The nearest neighbor search problem arises in numerous fields of application, including:
* [Pattern recognition](</wiki/Pattern_recognition> "Pattern recognition") – in particular for [optical character recognition](</wiki/Optical_character_recognition> "Optical character recognition")
* [Statistical classification](</wiki/Statistical_classification> "Statistical classification") – see [k-nearest neighbor algorithm](</wiki/K-nearest_neighbor_algorithm> "K-nearest neighbor algorithm")
* [Computer vision](</wiki/Computer_vision> "Computer vision") – for [point cloud registration](</wiki/Point_cloud_registration> "Point cloud registration")[2]
* [Computational geometry](</wiki/Computational_geometry> "Computational geometry") – see [Closest pair of points problem](</wiki/Closest_pair_of_points_problem> "Closest pair of points problem")
* [Cryptanalysis](</wiki/Cryptanalysis> "Cryptanalysis") – for [lattice problem](</wiki/Lattice_problem> "Lattice problem")[3]
* [Databases](</wiki/Database> "Database") – e.g. [content-based image retrieval](</wiki/Content-based_image_retrieval> "Content-based image retrieval")
* [Coding theory](</wiki/Coding_theory> "Coding theory") – see [maximum likelihood decoding](</wiki/Decoding_methods> "Decoding methods")
* [Semantic search](</wiki/Semantic_search> "Semantic search")
* [Data compression](</wiki/Data_compression> "Data compression") – see [MPEG-2](</wiki/MPEG-2> "MPEG-2") standard
* [Robotic](</wiki/Robotic> "Robotic") sensing[4]
* [Recommendation systems](</wiki/Recommender_system> "Recommender system"), e.g. see [Collaborative filtering](</wiki/Collaborative_filtering> "Collaborative filtering")
* [Internet marketing](</wiki/Internet_marketing> "Internet marketing") – see [contextual advertising](</wiki/Contextual_advertising> "Contextual advertising") and [behavioral targeting](</wiki/Behavioral_targeting> "Behavioral targeting")
* [DNA sequencing](</wiki/DNA_sequencing> "DNA sequencing")
* [Spell checking](</wiki/Spell_checking> "Spell checking") – suggesting correct spelling
* [Plagiarism detection](</wiki/Plagiarism_detection> "Plagiarism detection")
* [Similarity scores](</wiki/Similarity_score> "Similarity score") for predicting career paths of professional athletes.
* [Cluster analysis](</wiki/Cluster_analysis> "Cluster analysis") – assignment of a set of observations into subsets (called clusters) so that observations in the same cluster are similar in some sense, usually based on [Euclidean distance](</wiki/Euclidean_distance> "Euclidean distance")
* [Chemical similarity](</wiki/Chemical_similarity> "Chemical similarity")
* [Sampling-based motion planning](</wiki/Motion_planning#Sampling-based_algorithms> "Motion planning")
## Methods
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=2> "Edit section: Methods")]
Various solutions to the NNS problem have been proposed. The quality and usefulness of the algorithms are determined by the time complexity of queries as well as the space complexity of any search data structures that must be maintained. The informal observation usually referred to as the [curse of dimensionality](</wiki/Curse_of_dimensionality> "Curse of dimensionality") states that there is no general-purpose exact solution for NNS in high-dimensional Euclidean space using polynomial preprocessing and polylogarithmic search time.
### Exact methods
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=3> "Edit section: Exact methods")]
#### Linear search
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=4> "Edit section: Linear search")]
The simplest solution to the NNS problem is to compute the distance from the query point to every other point in the database, keeping track of the "best so far". This algorithm, sometimes referred to as the naive approach, has a [running time](</wiki/Running_time> "Running time") of _O_(_dN_), where _N_ is the [cardinality](</wiki/Cardinality> "Cardinality") of _S_ and _d_ is the dimensionality of _S_. There are no search data structures to maintain, so the linear search has no space complexity beyond the storage of the database. Naive search can, on average, outperform space partitioning approaches on higher dimensional spaces.[5]
The absolute distance is not required for distance comparison, only the relative distance. In geometric coordinate systems the distance calculation can be sped up considerably by omitting the square root calculation from the distance calculation between two coordinates. The distance comparison will still yield identical results.
#### Space partitioning
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=5> "Edit section: Space partitioning")]
Since the 1970s, the [branch and bound](</wiki/Branch_and_bound> "Branch and bound") methodology has been applied to the problem. In the case of Euclidean space, this approach encompasses [spatial index](</wiki/Spatial_index> "Spatial index") or spatial access methods. Several [space-partitioning](</wiki/Space_partitioning> "Space partitioning") methods have been developed for solving the NNS problem. Perhaps the simplest is the [k-d tree](</wiki/K-d_tree> "K-d tree"), which iteratively bisects the search space into two regions containing half of the points of the parent region. Queries are performed via traversal of the tree from the root to a leaf by evaluating the query point at each split. Depending on the distance specified in the query, neighboring branches that might contain hits may also need to be evaluated. For constant dimension query time, average complexity is _O_(log  _N_)[6] in the case of randomly distributed points, worst case complexity is _O_(_kN_ ^(1-1/_k_))[7] Alternatively the [R-tree](</wiki/R-tree> "R-tree") data structure was designed to support nearest neighbor search in dynamic context, as it has efficient algorithms for insertions and deletions such as the [R
* tree](</wiki/R
* _tree> "R
* tree").[8] R-trees can yield nearest neighbors not only for Euclidean distance, but can also be used with other distances.
In the case of general metric space, the branch-and-bound approach is known as the [metric tree](</wiki/Metric_tree> "Metric tree") approach. Particular examples include [vp-tree](</wiki/Vp-tree> "Vp-tree") and [BK-tree](</wiki/BK-tree> "BK-tree") methods.
Using a set of points taken from a 3-dimensional space and put into a [BSP tree](</wiki/Binary_space_partitioning> "Binary space partitioning"), and given a query point taken from the same space, a possible solution to the problem of finding the nearest point-cloud point to the query point is given in the following description of an algorithm.
| This article
* may be[confusing or unclear](</wiki/Wikipedia:Vagueness> "Wikipedia:Vagueness") to readers
* . Please help [clarify the article](</wiki/Wikipedia:Please_clarify> "Wikipedia:Please clarify"). There might be a discussion about this on [the talk page](</wiki/Talk:Nearest_neighbor_search> "Talk:Nearest neighbor search"). _( November 2021)__([Learn how and when to remove this message](</wiki/Help:Maintenance_template_removal> "Help:Maintenance template removal"))_
---|---
(Strictly speaking, no such point may exist, because it may not be unique. But in practice, usually we only care about finding any one of the subset of all point-cloud points that exist at the shortest distance to a given query point.) The idea is, for each branching of the tree, guess that the closest point in the cloud resides in the half-space containing the query point. This may not be the case, but it is a good heuristic. After having recursively gone through all the trouble of solving the problem for the guessed half-space, now compare the distance returned by this result with the shortest distance from the query point to the partitioning plane. This latter distance is that between the query point and the closest possible point that could exist in the half-space not searched. If this distance is greater than that returned in the earlier result, then clearly there is no need to search the other half-space. If there is such a need, then you must go through the trouble of solving the problem for the other half space, and then compare its result to the former result, and then return the proper result. The performance of this algorithm is nearer to logarithmic time than linear time when the query point is near the cloud, because as the distance between the query point and the closest point-cloud point nears zero, the algorithm needs only perform a look-up using the query point as a key to get the correct result.
### Approximation methods
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=6> "Edit section: Approximation methods")]
An approximate nearest neighbor search algorithm is allowed to return points whose distance from the query is at most  c {\displaystyle c} times the distance from the query to its nearest points. The appeal of this approach is that, in many cases, an approximate nearest neighbor is almost as good as the exact one. In particular, if the distance measure accurately captures the notion of user quality, then small differences in the distance should not matter.[9]
#### Greedy search in proximity neighborhood graphs
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=7> "Edit section: Greedy search in proximity neighborhood graphs")]
Proximity graph methods (such as navigable small world graphs[10] and [HNSW](</wiki/Hierarchical_Navigable_Small_World_graphs> "Hierarchical Navigable Small World graphs")[11][12]) are considered the current state-of-the-art for the approximate nearest neighbors search.
The methods are based on greedy traversing in proximity neighborhood graphs  G ( V , E ) {\displaystyle G(V,E)} in which every point  x i ∈ S {\displaystyle x_{i}\in S} is uniquely associated with vertex  v i ∈ V {\displaystyle v_{i}\in V} . The search for the nearest neighbors to a query _q_ in the set _S_ takes the form of searching for the vertex in the graph  G ( V , E ) {\displaystyle G(V,E)} . The basic algorithm – greedy search – works as follows: search starts from an enter-point vertex  v i ∈ V {\displaystyle v_{i}\in V} by computing the distances from the query q to each vertex of its neighborhood  { v j : ( v i , v j ) ∈ E } {\displaystyle \\{v_{j}:(v_{i},v_{j})\in E\\}} , and then finds a vertex with the minimal distance value. If the distance value between the query and the selected vertex is smaller than the one between the query and the current element, then the algorithm moves to the selected vertex, and it becomes new enter-point. The algorithm stops when it reaches a local minimum: a vertex whose neighborhood does not contain a vertex that is closer to the query than the vertex itself.
The idea of proximity neighborhood graphs was exploited in multiple publications, including the seminal paper by Arya and Mount,[13] in the VoroNet system for the plane,[14] in the RayNet system for the  E n {\displaystyle \mathbb {E} ^{n}} ,[15] and in the Navigable Small World,[10] Metrized Small World[16] and [HNSW](</wiki/Hierarchical_Navigable_Small_World_graphs> "Hierarchical Navigable Small World graphs")[11][12] algorithms for the general case of spaces with a distance function. These works were preceded by a pioneering paper by Toussaint, in which he introduced the concept of a _relative neighborhood_ graph.[17]
#### Locality sensitive hashing
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=8> "Edit section: Locality sensitive hashing")]
[Locality sensitive hashing](</wiki/Locality_sensitive_hashing> "Locality sensitive hashing") (LSH) is a technique for grouping points in space into 'buckets' based on some distance metric operating on the points. Points that are close to each other under the chosen metric are mapped to the same bucket with high probability.[18]
#### Nearest neighbor search in spaces with small intrinsic dimension
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=9> "Edit section: Nearest neighbor search in spaces with small intrinsic dimension")]
See also: [Intrinsic dimension](</wiki/Intrinsic_dimension> "Intrinsic dimension")
The [cover tree](</wiki/Cover_tree> "Cover tree") has a theoretical bound that is based on the dataset's [doubling constant](</wiki/Doubling_space> "Doubling space"). The bound on search time is _O_(_c_ 12 log  _n_) where _c_ is the [expansion constant](</wiki/Expansivity_constant> "Expansivity constant") of the dataset.
#### Projected radial search
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=10> "Edit section: Projected radial search")]
In the special case where the data is a dense 3D map of geometric points, the projection geometry of the sensing technique can be used to dramatically simplify the search problem. This approach requires that the 3D data is organized by a projection to a two-dimensional grid and assumes that the data is spatially smooth across neighboring grid cells with the exception of object boundaries. These assumptions are valid when dealing with 3D sensor data in applications such as surveying, robotics and stereo vision but may not hold for unorganized data in general. In practice this technique has an average search time of _O_(_1_) or _O_(_K_) for the _k_ -nearest neighbor problem when applied to real world stereo vision data.[4]
#### Vector approximation files
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=11> "Edit section: Vector approximation files")]
In high-dimensional spaces, tree indexing structures become useless because an increasing percentage of the nodes need to be examined anyway. To speed up linear search, a compressed version of the feature vectors stored in RAM is used to prefilter the datasets in a first run. The final candidates are determined in a second stage using the uncompressed data from the disk for distance calculation.[19]
#### Compression/clustering based search
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=12> "Edit section: Compression/clustering based search")]
The VA-file approach is a special case of a compression based search, where each feature component is compressed uniformly and independently. The optimal compression technique in multidimensional spaces is [Vector Quantization](</wiki/Vector_Quantization> "Vector Quantization") (VQ), implemented through clustering. The database is clustered and the most "promising" clusters are retrieved. Huge gains over VA-File, tree-based indexes and sequential scan have been observed.[20][21] Also note the parallels between clustering and LSH.
## Variants
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=13> "Edit section: Variants")]
There are numerous variants of the NNS problem and the two most well-known are the [_k_ -nearest neighbor search](</wiki/K-nearest_neighbor_algorithm> "K-nearest neighbor algorithm") and the [ε-approximate nearest neighbor search](</wiki/%CE%95-approximate_nearest_neighbor_search> "Ε-approximate nearest neighbor search").
###  _k_ -nearest neighbors
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=14> "Edit section: k-nearest neighbors")]
[_k_ -nearest neighbor search](</wiki/K-nearest_neighbor_algorithm> "K-nearest neighbor algorithm") identifies the top _k_ nearest neighbors to the query. This technique is commonly used in [predictive analytics](</wiki/Predictive_analytics> "Predictive analytics") to estimate or classify a point based on the consensus of its neighbors. _k_ -nearest neighbor graphs are graphs in which every point is connected to its _k_ nearest neighbors.
### Approximate nearest neighbor
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=15> "Edit section: Approximate nearest neighbor")]
In some applications it may be acceptable to retrieve a "good guess" of the nearest neighbor. In those cases, we can use an algorithm which doesn't guarantee to return the actual nearest neighbor in every case, in return for improved speed or memory savings. Often such an algorithm will find the nearest neighbor in a majority of cases, but this depends strongly on the dataset being queried.
Algorithms that support the approximate nearest neighbor search include [locality-sensitive hashing](</wiki/Locality-sensitive_hashing#Algorithm_for_nearest_neighbor_search> "Locality-sensitive hashing"), [best bin first](</wiki/Best_bin_first> "Best bin first") and [balanced box-decomposition tree](</w/index.php?title=Balanced_box-decomposition_tree&action=edit&redlink=1> "Balanced box-decomposition tree \(page does not exist\)") based search.[22]
### Nearest neighbor distance ratio
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=16> "Edit section: Nearest neighbor distance ratio")]
[Nearest neighbor distance ratio](</wiki/Nearest_neighbor_distance_ratio> "Nearest neighbor distance ratio") does not apply the threshold on the direct distance from the original point to the challenger neighbor but on a ratio of it depending on the distance to the previous neighbor. It is used in [CBIR](</wiki/Content-based_image_retrieval> "Content-based image retrieval") to retrieve pictures through a "query by example" using the similarity between local features. More generally it is involved in several [matching](</wiki/Pattern_matching> "Pattern matching") problems.
### Fixed-radius near neighbors
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=17> "Edit section: Fixed-radius near neighbors")]
[Fixed-radius near neighbors](</wiki/Fixed-radius_near_neighbors> "Fixed-radius near neighbors") is the problem where one wants to efficiently find all points given in [Euclidean space](</wiki/Euclidean_space> "Euclidean space") within a given fixed distance from a specified point. The distance is assumed to be fixed, but the query point is arbitrary.
### All nearest neighbors
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=18> "Edit section: All nearest neighbors")]
For some applications (e.g. [entropy estimation](</wiki/Entropy_estimation> "Entropy estimation")), we may have _N_ data-points and wish to know which is the nearest neighbor _for every one of those N points_. This could, of course, be achieved by running a nearest-neighbor search once for every point, but an improved strategy would be an algorithm that exploits the information redundancy between these _N_ queries to produce a more efficient search. As a simple example: when we find the distance from point _X_ to point _Y_ , that also tells us the distance from point _Y_ to point _X_ , so the same calculation can be reused in two different queries.
Given a fixed dimension, a semi-definite positive norm (thereby including every [Lp norm](</wiki/Lp_space> "Lp space")), and _n_ points in this space, the nearest neighbour of every point can be found in _O_(_n_ log  _n_) time and the _m_ nearest neighbours of every point can be found in _O_(_mn_ log  _n_) time.[23][24]
## See also
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=19> "Edit section: See also")]
* [Ball tree](</wiki/Ball_tree> "Ball tree")
* [Closest pair of points problem](</wiki/Closest_pair_of_points_problem> "Closest pair of points problem")
* [Cluster analysis](</wiki/Cluster_analysis> "Cluster analysis")
* [Content-based image retrieval](</wiki/Content-based_image_retrieval> "Content-based image retrieval")
* [Curse of dimensionality](</wiki/Curse_of_dimensionality> "Curse of dimensionality")
* [Digital signal processing](</wiki/Digital_signal_processing> "Digital signal processing")
* [Dimension reduction](</wiki/Dimension_reduction> "Dimension reduction")
* [Fixed-radius near neighbors](</wiki/Fixed-radius_near_neighbors> "Fixed-radius near neighbors")
* [Fourier analysis](</wiki/Fourier_analysis> "Fourier analysis")
* [Instance-based learning](</wiki/Instance-based_learning> "Instance-based learning")
* [_k_ -nearest neighbor algorithm](</wiki/K-nearest_neighbor_algorithm> "K-nearest neighbor algorithm")
* [Linear least squares](</wiki/Linear_least_squares_\(mathematics\)> "Linear least squares \(mathematics\)")
* [Locality sensitive hashing](</wiki/Locality_sensitive_hashing> "Locality sensitive hashing")
* [Maximum inner-product search](</wiki/Maximum_inner-product_search> "Maximum inner-product search")
* [MinHash](</wiki/MinHash> "MinHash")
* [Multidimensional analysis](</wiki/Multidimensional_analysis> "Multidimensional analysis")
* [Nearest-neighbor interpolation](</wiki/Nearest-neighbor_interpolation> "Nearest-neighbor interpolation")
* [Neighbor joining](</wiki/Neighbor_joining> "Neighbor joining")
* [Principal component analysis](</wiki/Principal_component_analysis> "Principal component analysis")
* [Range search](</wiki/Range_search> "Range search")
* [Similarity learning](</wiki/Similarity_learning> "Similarity learning")
* [Singular value decomposition](</wiki/Singular_value_decomposition> "Singular value decomposition")
* [Sparse distributed memory](</wiki/Sparse_distributed_memory> "Sparse distributed memory")
* [Statistical distance](</wiki/Statistical_distance> "Statistical distance")
* [Time series](</wiki/Time_series> "Time series")
* [Voronoi diagram](</wiki/Voronoi_diagram> "Voronoi diagram")
* [Wavelet](</wiki/Wavelet> "Wavelet")
## References
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=20> "Edit section: References")]
### Citations
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=21> "Edit section: Citations")]
1.
* ^
* Cayton, Lawerence (2008). "Fast nearest neighbor retrieval for bregman divergences". _Proceedings of the 25th International Conference on Machine Learning_. pp. 112–119\. [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1145/1390156.1390171](<https://doi.org/10.1145%2F1390156.1390171>). [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [9781605582054](</wiki/Special:BookSources/9781605582054> "Special:BookSources/9781605582054"). [S2CID](</wiki/S2CID_\(identifier\)> "S2CID \(identifier\)") [12169321](<https://api.semanticscholar.org/CorpusID:12169321>).
2.
* ^
* Qiu, Deyuan, Stefan May, and Andreas Nüchter. ["GPU-accelerated nearest neighbor search for 3D registration."](<https://core.ac.uk/download/pdf/22872975.pdf>) International conference on computer vision systems. Springer, Berlin, Heidelberg, 2009.
3.
* ^
* Becker, Ducas, Gama, and Laarhoven. ["New directions in nearest neighbor searching with applications to lattice sieving."](<https://eprint.iacr.org/2015/1128.pdf>) Proceedings of the twenty-seventh annual ACM-SIAM symposium on Discrete algorithms (pp. 10-24). Society for Industrial and Applied Mathematics.
4. ^ _
* a
* b
* _ Bewley, A.; Upcroft, B. (2013). [_Advantages of Exploiting Projection Structure for Segmenting Dense 3D Point Clouds_](<http://www.araa.asn.au/acra/acra2013/papers/pap148s1-file1.pdf>) (PDF). Australian Conference on Robotics and Automation.
5.
* ^
* Weber, Roger; Schek, Hans-J.; Blott, Stephen (1998). ["A quantitative analysis and performance study for similarity search methods in high dimensional spaces"](<http://www.vldb.org/conf/1998/p194.pdf>) (PDF). _VLDB '98 Proceedings of the 24rd International Conference on Very Large Data Bases_. pp. 194–205.
6.
* ^
* Andrew Moore. ["An introductory tutorial on KD trees"](<https://web.archive.org/web/20160303203122/http://www.autonlab.com/autonweb/14665/version/2/part/5/data/moore-tutorial.pdf?branch=main&language=en>) (PDF). Archived from [the original](<http://www.autonlab.com/autonweb/14665/version/2/part/5/data/moore-tutorial.pdf?branch=main&language=en>) (PDF) on 2016-03-03. Retrieved 2008-10-03.
7.
* ^
* [Lee, D. T.](</wiki/Der-Tsai_Lee> "Der-Tsai Lee"); Wong, C. K. (1977). "Worst-case analysis for region and partial region searches in multidimensional binary search trees and balanced quad trees". _[Acta Informatica](</wiki/Acta_Informatica> "Acta Informatica")_.
* 9
* (1): 23–29\. [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1007/BF00263763](<https://doi.org/10.1007%2FBF00263763>). [S2CID](</wiki/S2CID_\(identifier\)> "S2CID \(identifier\)") [36580055](<https://api.semanticscholar.org/CorpusID:36580055>).
8.
* ^
* Roussopoulos, N.; Kelley, S.; Vincent, F. D. R. (1995). "Nearest neighbor queries". _Proceedings of the 1995 ACM SIGMOD international conference on Management of data – SIGMOD '95_. p. 71. [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1145/223784.223794](<https://doi.org/10.1145%2F223784.223794>). [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [0897917316](</wiki/Special:BookSources/0897917316> "Special:BookSources/0897917316").
9.
* ^
* Andoni, A.; Indyk, P. (2006-10-01). "Near-Optimal Hashing Algorithms for Approximate Nearest Neighbor in High Dimensions". _2006 47th Annual IEEE Symposium on Foundations of Computer Science (FOCS'06)_. pp. 459–468\. [CiteSeerX](</wiki/CiteSeerX_\(identifier\)> "CiteSeerX \(identifier\)") [10.1.1.142.3471](<https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.142.3471>). [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1109/FOCS.2006.49](<https://doi.org/10.1109%2FFOCS.2006.49>). [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-0-7695-2720-8](</wiki/Special:BookSources/978-0-7695-2720-8> "Special:BookSources/978-0-7695-2720-8").
10. ^ _
* a
* b
* _ Malkov, Yury; Ponomarenko, Alexander; Logvinov, Andrey; Krylov, Vladimir (2012), Navarro, Gonzalo; Pestov, Vladimir (eds.), ["Scalable Distributed Algorithm for Approximate Nearest Neighbor Search Problem in High Dimensional General Metric Spaces"](<http://link.springer.com/10.1007/978-3-642-32153-5_10>), _Similarity Search and Applications_ , vol. 7404, Berlin, Heidelberg: Springer Berlin Heidelberg, pp. 132–147, [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1007/978-3-642-32153-5_10](<https://doi.org/10.1007%2F978-3-642-32153-5_10>), [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-3-642-32152-8](</wiki/Special:BookSources/978-3-642-32152-8> "Special:BookSources/978-3-642-32152-8"), retrieved 2024-01-16
11. ^ _
* a
* b
* _ Malkov, Yury; Yashunin, Dmitry (2016). "Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs". [arXiv](</wiki/ArXiv_\(identifier\)> "ArXiv \(identifier\)"):[1603.09320](<https://arxiv.org/abs/1603.09320>) [[cs.DS](<https://arxiv.org/archive/cs.DS>)].
12. ^ _
* a
* b
* _ Malkov, Yu A.; Yashunin, D. A. (2020-04-01). "Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs". _IEEE Transactions on Pattern Analysis and Machine Intelligence_.
* 42
* (4): 824–836\. [arXiv](</wiki/ArXiv_\(identifier\)> "ArXiv \(identifier\)"):[1603.09320](<https://arxiv.org/abs/1603.09320>). [Bibcode](</wiki/Bibcode_\(identifier\)> "Bibcode \(identifier\)"):[2020ITPAM..42..824M](<https://ui.adsabs.harvard.edu/abs/2020ITPAM..42..824M>). [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1109/TPAMI.2018.2889473](<https://doi.org/10.1109%2FTPAMI.2018.2889473>). [ISSN](</wiki/ISSN_\(identifier\)> "ISSN \(identifier\)") [0162-8828](<https://search.worldcat.org/issn/0162-8828>). [PMID](</wiki/PMID_\(identifier\)> "PMID \(identifier\)") [30602420](<https://pubmed.ncbi.nlm.nih.gov/30602420>).
13.
* ^
* Arya, Sunil; Mount, David (1993). "Approximate Nearest Neighbor Queries in Fixed Dimensions". _Proceedings of the Fourth Annual {ACM/SIGACT-SIAM} Symposium on Discrete Algorithms, 25–27 January 1993, Austin, Texas._ : 271–280.
14.
* ^
* Olivier, Beaumont; Kermarrec, Anne-Marie; Marchal, Loris; Rivière, Etienne (2006). ["Voro _Net_ : A scalable object network based on Voronoi tessellations"](<https://hal.inria.fr/inria-00071210/PDF/RR-5833.pdf>) (PDF). _2007 IEEE International Parallel and Distributed Processing Symposium_. Vol. RR-5833. pp. 23–29\. [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1109/IPDPS.2007.370210](<https://doi.org/10.1109%2FIPDPS.2007.370210>). [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [1-4244-0909-8](</wiki/Special:BookSources/1-4244-0909-8> "Special:BookSources/1-4244-0909-8"). [S2CID](</wiki/S2CID_\(identifier\)> "S2CID \(identifier\)") [8844431](<https://api.semanticscholar.org/CorpusID:8844431>).
15.
* ^
* Olivier, Beaumont; Kermarrec, Anne-Marie; Rivière, Etienne (2007). "Peer to Peer Multidimensional Overlays: Approximating Complex Structures". _Principles of Distributed Systems_. Lecture Notes in Computer Science. Vol. 4878. pp. 315–328\. [CiteSeerX](</wiki/CiteSeerX_\(identifier\)> "CiteSeerX \(identifier\)") [10.1.1.626.2980](<https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.626.2980>). [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1007/978-3-540-77096-1_23](<https://doi.org/10.1007%2F978-3-540-77096-1_23>). [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-3-540-77095-4](</wiki/Special:BookSources/978-3-540-77095-4> "Special:BookSources/978-3-540-77095-4").
16.
* ^
* Malkov, Yury; Ponomarenko, Alexander; Krylov, Vladimir; Logvinov, Andrey (2014). "Approximate nearest neighbor algorithm based on navigable small world graphs". _Information Systems_.
* 45
* : 61–68\. [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1016/j.is.2013.10.006](<https://doi.org/10.1016%2Fj.is.2013.10.006>). [S2CID](</wiki/S2CID_\(identifier\)> "S2CID \(identifier\)") [9896397](<https://api.semanticscholar.org/CorpusID:9896397>).
17.
* ^
* Toussaint, Godfried (1980). "The relative neighbourhood graph of a finite planar set". _Pattern Recognition_.
* 12
* (4): 261–268\. [Bibcode](</wiki/Bibcode_\(identifier\)> "Bibcode \(identifier\)"):[1980PatRe..12..261T](<https://ui.adsabs.harvard.edu/abs/1980PatRe..12..261T>). [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1016/0031-3203(80)90066-7](<https://doi.org/10.1016%2F0031-3203%2880%2990066-7>).
18.
* ^
* A. Rajaraman & J. Ullman (2010). ["Mining of Massive Datasets, Ch. 3"](<http://infolab.stanford.edu/~ullman/mmds.html>).
19.
* ^
* Weber, Roger; Blott, Stephen. ["An Approximation-Based Data Structure for Similarity Search"](<https://web.archive.org/web/20170304043243/https://pdfs.semanticscholar.org/83e4/e3281411ffef40654a4b5d29dae48130aefb.pdf>) (PDF). [S2CID](</wiki/S2CID_\(identifier\)> "S2CID \(identifier\)") [14613657](<https://api.semanticscholar.org/CorpusID:14613657>). Archived from [the original](<https://pdfs.semanticscholar.org/83e4/e3281411ffef40654a4b5d29dae48130aefb.pdf>) (PDF) on 2017-03-04. `{{[cite journal](</wiki/Template:Cite_journal> "Template:Cite journal")}}`: Cite journal requires `|journal=` ([help](</wiki/Help:CS1_errors#missing_periodical> "Help:CS1 errors"))
20.
* ^
* Ramaswamy, Sharadh; Rose, Kenneth (2007). "Adaptive cluster-distance bounding for similarity search in image databases". _ICIP_.
21.
* ^
* Ramaswamy, Sharadh; Rose, Kenneth (2010). "Adaptive cluster-distance bounding for high-dimensional indexing". _TKDE_.
22.
* ^
* Arya, S.; [Mount, D. M.](</wiki/David_Mount> "David Mount"); [Netanyahu, N. S.](</wiki/Nathan_Netanyahu> "Nathan Netanyahu"); Silverman, R.; Wu, A. (1998). ["An optimal algorithm for approximate nearest neighbor searching"](<https://web.archive.org/web/20160303232202/http://www.cse.ust.hk/faculty/arya/pub/JACM.pdf>) (PDF). _Journal of the ACM_.
* 45
* (6): 891–923\. [CiteSeerX](</wiki/CiteSeerX_\(identifier\)> "CiteSeerX \(identifier\)") [10.1.1.15.3125](<https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.15.3125>). [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1145/293347.293348](<https://doi.org/10.1145%2F293347.293348>). [S2CID](</wiki/S2CID_\(identifier\)> "S2CID \(identifier\)") [8193729](<https://api.semanticscholar.org/CorpusID:8193729>). Archived from [the original](<http://www.cse.ust.hk/faculty/arya/pub/JACM.pdf>) (PDF) on 2016-03-03. Retrieved 2009-05-29.
23.
* ^
* [Clarkson, Kenneth L.](</wiki/Kenneth_L._Clarkson> "Kenneth L. Clarkson") (1983), "Fast algorithms for the all nearest neighbors problem", _24th IEEE Symp. Foundations of Computer Science, (FOCS '83)_ , pp. 226–232, [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1109/SFCS.1983.16](<https://doi.org/10.1109%2FSFCS.1983.16>), [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-0-8186-0508-6](</wiki/Special:BookSources/978-0-8186-0508-6> "Special:BookSources/978-0-8186-0508-6"), [S2CID](</wiki/S2CID_\(identifier\)> "S2CID \(identifier\)") [16665268](<https://api.semanticscholar.org/CorpusID:16665268>).
24.
* ^
* Vaidya, P. M. (1989). ["An _O_(_n_ log  _n_) Algorithm for the All-Nearest-Neighbors Problem"](<https://doi.org/10.1007%2FBF02187718>). _[Discrete and Computational Geometry](</wiki/Discrete_and_Computational_Geometry> "Discrete and Computational Geometry")_.
* 4
* (1): 101–115\. [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1007/BF02187718](<https://doi.org/10.1007%2FBF02187718>).
### Sources
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=22> "Edit section: Sources")]
* Andrews, L. (November 2001). ["A template for the nearest neighbor problem"](<http://www.ddj.com/architect/184401449>). _C/C++ Users Journal_. **19** (11): 40–49\. [ISSN](</wiki/ISSN_\(identifier\)> "ISSN \(identifier\)") [1075-2838](<https://search.worldcat.org/issn/1075-2838>).
* Arya, S.; [Mount, D.M.](</wiki/David_Mount> "David Mount"); [Netanyahu, N. S.](</wiki/Nathan_Netanyahu> "Nathan Netanyahu"); [Silverman, R.](</wiki/Ruth_Silverman> "Ruth Silverman"); [Wu, A. Y.](</wiki/Angela_Y._Wu> "Angela Y. Wu") (1998). "An Optimal Algorithm for Approximate Nearest Neighbor Searching in Fixed Dimensions". _Journal of the ACM_. **45** (6): 891–923\. [CiteSeerX](</wiki/CiteSeerX_\(identifier\)> "CiteSeerX \(identifier\)") [10.1.1.15.3125](<https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.15.3125>). [doi](</wiki/Doi_\(identifier\)> "Doi \(identifier\)"):[10.1145/293347.293348](<https://doi.org/10.1145%2F293347.293348>). [S2CID](</wiki/S2CID_\(identifier\)> "S2CID \(identifier\)") [8193729](<https://api.semanticscholar.org/CorpusID:8193729>).
* Beyer, K.; Goldstein, J.; Ramakrishnan, R.; Shaft, U. (1999). "When is nearest neighbor meaningful?". _Proceedings of the 7th ICDT_.
* Chen, Chung-Min; Ling, Yibei (2002). "A Sampling-Based Estimator for Top-k Query". _ICDE_ : 617–627.
* [Samet, H.](</wiki/Hanan_Samet> "Hanan Samet") (2006). _Foundations of Multidimensional and Metric Data Structures_. Morgan Kaufmann. [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-0-12-369446-1](</wiki/Special:BookSources/978-0-12-369446-1> "Special:BookSources/978-0-12-369446-1").
* Zezula, P.; Amato, G.; Dohnal, V.; Batko, M. (2006). _Similarity Search – The Metric Space Approach_. Springer. [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-0-387-29146-8](</wiki/Special:BookSources/978-0-387-29146-8> "Special:BookSources/978-0-387-29146-8").
## Further reading
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=23> "Edit section: Further reading")]
* Shasha, Dennis (2004). _High Performance Discovery in Time Series_. Berlin: Springer. [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-0-387-00857-8](</wiki/Special:BookSources/978-0-387-00857-8> "Special:BookSources/978-0-387-00857-8").
## External links
[[edit](</w/index.php?title=Nearest_neighbor_search&action=edit&section=24> "Edit section: External links")]
[](</wiki/File:Commons-logo.svg>)
Wikimedia Commons has media related to [Nearest neighbours search](<https://commons.wikimedia.org/wiki/Category:Nearest_neighbours_search> "commons:Category:Nearest neighbours search").
* [Nearest Neighbors and Similarity Search](<http://simsearch.yury.name/tutorial.html>) – a website dedicated to educational materials, software, literature, researchers, open problems and events related to NN searching. Maintained by Yury Lifshits
* [Similarity Search Wiki](<https://archive.today/20130222061350/http://sswiki.tierra-aoi.net/>) – a collection of links, people, ideas, keywords, papers, slides, code and data sets on nearest neighbours
Retrieved from "[https://en.wikipedia.org/w/index.php?title=Nearest_neighbor_search&oldid=1308006314#Approximation_methods](<https://en.wikipedia.org/w/index.php?title=Nearest_neighbor_search&oldid=1308006314#Approximation_methods>)"
[Categories](</wiki/Help:Category> "Help:Category"):
* [Approximation algorithms](</wiki/Category:Approximation_algorithms> "Category:Approximation algorithms")
* [Classification algorithms](</wiki/Category:Classification_algorithms> "Category:Classification algorithms")
* [Data mining](</wiki/Category:Data_mining> "Category:Data mining")
* [Discrete geometry](</wiki/Category:Discrete_geometry> "Category:Discrete geometry")
* [Geometric algorithms](</wiki/Category:Geometric_algorithms> "Category:Geometric algorithms")
* [Mathematical optimization](</wiki/Category:Mathematical_optimization> "Category:Mathematical optimization")
* [Search algorithms](</wiki/Category:Search_algorithms> "Category:Search algorithms")
Hidden categories:
* [CS1: long volume value](</wiki/Category:CS1:_long_volume_value> "Category:CS1: long volume value")
* [CS1 errors: missing periodical](</wiki/Category:CS1_errors:_missing_periodical> "Category:CS1 errors: missing periodical")
* [Articles with short description](</wiki/Category:Articles_with_short_description> "Category:Articles with short description")
* [Short description is different from Wikidata](</wiki/Category:Short_description_is_different_from_Wikidata> "Category:Short description is different from Wikidata")
* [Wikipedia articles needing clarification from November 2021](</wiki/Category:Wikipedia_articles_needing_clarification_from_November_2021> "Category:Wikipedia articles needing clarification from November 2021")
* [All Wikipedia articles needing clarification](</wiki/Category:All_Wikipedia_articles_needing_clarification> "Category:All Wikipedia articles needing clarification")
* [Commons category link is on Wikidata](</wiki/Category:Commons_category_link_is_on_Wikidata> "Category:Commons category link is on Wikidata")

---
*Document traité automatiquement par le système de recherche agentique*
