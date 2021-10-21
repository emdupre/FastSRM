from fastsrm2.srm import projection, detsrm, probsrm
from time import time
from fastsrm2.fastsrm import (
    fastsrm,
    reduce_rena,
    reduce_optimal,
    reduce_randomproj,
)
from fastsrm2.exp_utils import reg_error
import numpy as np
from joblib import delayed, Parallel
from brainiak.funcalign.srm import SRM, DetSRM


dim = (50, 50, 50)
m, v, k, n = 10, np.prod(dim), 50, 1000


def do_expe(it, seed, algo):
    rng = np.random.RandomState(seed)
    Sigma = rng.dirichlet(np.ones(k), 1).flatten()
    S = np.sqrt(Sigma)[:, None] * rng.randn(k, n)
    W = np.array([projection(rng.randn(v, k)) for i in range(m)])
    sigmas = 0.1 * rng.rand(m)
    N = np.array([sigmas[i] * rng.randn(v, n) for i in range(m)])
    X = np.array([W[i].dot(S) + N[i] for i in range(m)])
    S_true = S

    def to_niimgs(Xt, dim):
        X = np.copy(Xt).T
        from nilearn.masking import _unmask_from_to_3d_array
        import nibabel

        p = np.prod(dim)
        assert len(dim) == 3
        assert X.shape[-1] <= p
        mask = np.zeros(p).astype(np.bool)
        mask[: X.shape[-1]] = 1
        assert mask.sum() == X.shape[1]
        mask = mask.reshape(dim)
        X = np.rollaxis(
            np.array([_unmask_from_to_3d_array(x, mask) for x in X]),
            0,
            start=4,
        )
        affine = np.eye(4)
        return (
            nibabel.Nifti1Image(X, affine),
            nibabel.Nifti1Image(mask.astype(np.float), affine),
        )

    _, mask = to_niimgs(X[0], dim)

    t0 = time()
    if algo == "brainiakdetsrm":
        S = DetSRM(n_iter=it, features=k, rand_seed=0).fit(X).s_
    if algo == "brainiakprobsrm":
        S = SRM(n_iter=it, features=k, rand_seed=0).fit(X).s_
    if algo == "detsrm":
        S = detsrm(X, k, n_iter=it, random_state=rng)[1]
    if algo == "probsrm":
        S = probsrm(X, k, n_iter=it, random_state=rng)[1]
    if "fastsrm" in algo:
        algo_name, method, func_name, n_regions = algo.split("_")
        if func_name == "pca":
            func = reduce_optimal
        if func_name == "rena":
            func = reduce_rena
        if func_name == "proj":
            func = reduce_randomproj
        S = fastsrm(
            X,
            k,
            n_iter=it,
            method=method,
            n_regions=int(n_regions),
            mask=mask,
            func=func,
            random_state=rng,
        )[1]
    return reg_error(S_true, S), time() - t0, it, seed, algo, grad


# algos = ["probsrm", "detsrm", "brainiakdetsrm", "brainiakprobsrm"]
# # for method in ["prob", "det"]:
# #     for func_name in ["pca", "rena", "proj"]:
# #         for n_regions in [str(n), str(k)]:
# #             algos.append("fastsrm_%s_%s_%s" % (method, func_name, n_regions))
# for method in ["prob"]:
#     for func_name in ["pca", "rena", "proj"]:
#         for n_regions in [str(int(2 * n))]:
#             algos.append("fastsrm_%s_%s_%s" % (method, func_name, n_regions))
#     algos.append("fastsrm_%s_%s_%s" % (method, "pca", str(2 * k)))
# algos = []
# for method in ["prob"]:
#     for func_name in ["proj"]:
#         for n_regions in [str(int(20 * n))]:
#             algos.append("fastsrm_%s_%s_%s" % (method, func_name, n_regions))

# for method in ["prob"]:
#     for func_name in ["proj"]:
#         for n_regions in [str(int(v))]:
#             algos.append("fastsrm_%s_%s_%s" % (method, func_name, n_regions))

# algos = []
# for method in ["prob"]:
#     for func_name in ["proj"]:
#         for n_regions in [str(int(50 * n))]:
#             algos.append("fastsrm_%s_%s_%s" % (method, func_name, n_regions))

# # algos = []
# for method in ["prob"]:
#     for func_name in ["proj"]:
#         for n_regions in [str(int(100 * n))]:
#             algos.append("fastsrm_%s_%s_%s" % (method, func_name, n_regions))

algos = []
for method in ["prob", "det"]:
    algos.append("fastsrm_%s_%s_%s" % (method, func_name, n_regions))

iters = np.arange(1, 41, 5)
seeds = np.arange(30)
res = Parallel(n_jobs=10, verbose=10)(
    delayed(do_expe)(it, seed, algo)
    for it in iters
    for seed in seeds
    for algo in algos
)
a, b, c = len(iters), len(seeds), len(algos)
res = np.array(res)
res = res.reshape((a, b, c, -1))
for a, algo in enumerate(algos):
    np.save("../results/synthetic_%s.npy" % algo, res[:, :, a, :])
