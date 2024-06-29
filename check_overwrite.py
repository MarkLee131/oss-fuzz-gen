import os


# check the number of c/cpp files in the fixed_targets directory
def check_fixed_targets(directory: str) -> tuple:
  count = 0
  finish = False
  for root, dirs, files in os.walk(os.path.join(directory, "fixed_targets")):
    #  only check the direct childs of the project directory
    if root == os.path.join(directory, "fixed_targets"):
      for file in files:
        if file.endswith(".c") or file.endswith(".cpp") or file.endswith(".cc") \
        or file.endswith(".cxx"):
          count += 1
  if count < 5:
    print(f"Less than 5 c/cpp files in fixed_targets directory: {directory}")

  else:
    finish = True
  return count, finish


def parse_log(log_path: str):
  import re
  with open(log_path, 'r') as f:
    # Finished benchmark immer, result_t std::__1::tuple<unsigned int, immer::detail::rbts::node<int, immer::memory_policy<immer::heap_policy<immer::cpp_heap>, immer::unsafe_refcount_policy, immer::no_lock_policy, immer::no_transience_policy, false, true>, 2u, 2u>*, unsigned int, immer::detail::rbts::node<int, immer::memory_policy<immer::heap_policy<immer::cpp_heap>, immer::unsafe_refcount_policy, immer::no_lock_policy, immer::no_transience_policy, false, true>, 2u, 2u>*> immer::detail::rbts::slice_right_mut_visitor<immer::detail::rbts::node<int, immer::memory_policy<immer::heap_policy<immer::cpp_heap>, immer::unsafe_refcount_policy, immer::no_lock_policy, immer::no_transience_policy, false, true>, 2u, 2u>, true, true>::visit_regular<immer::detail::rbts::regular_pos<immer::detail::rbts::node<int, immer::memory_policy<immer::heap_policy<immer::cpp_heap>, immer::unsafe_refcount_policy, immer::no_lock_policy, immer::visit_regular<immer::detail::rbts::regular_sub_pos<immer::detail::rbts::node<int, immer::memory_policy<immer::heap_policy<immer::cpp_heap>, immer::unsafe_refcount_policy, immer::no_lock_policy, immer::no_transience_policy, true, true>, 3U, 3U> > &>(regular_sub_pos<immer::detail::rbts::node<int, immer::memory_policy<immer::heap_policy<immer::cpp_heap>, immer::unsafe_refcount_policy, immer::no_lock_policy, immer::no_transience_policy, true, true>, 3U, 3U> > &, size_t, edit_t) ****
    # parse the benchmark name and the function name

    projects_finished = []

    for line in f:

      if "Finished benchmark" in line:
        benchmark_name_re = re.search(r'Finished benchmark (.+?),', line)
        benchmark_name = benchmark_name_re.group(1) if benchmark_name_re else ""
        ## function_name is followed
        function_name_re = re.search(r'Finished benchmark .+?, (.+?) ', line)
        function_name = function_name_re.group(1) if function_name_re else ""
        # print(benchmark_name)
        # print(function_name)
        # print("\n")
        projects_finished.append(f"{benchmark_name}_{function_name}")
    return projects_finished


if __name__ == "__main__":

  # result_dir = '/home/kaixuan/FDG_LLM/oss-fuzz-gen/results'
  # project_dirs = [dir for dir in os.listdir(result_dir)]

  # for project_dir in project_dirs:
  #     # print(project_dir)
  #     project_dir = os.path.join(result_dir, project_dir)
  #     num, finish = check_fixed_targets(project_dir)
  #     if not finish:
  #         print(f"{project_dir} has {num} c/cpp files")
  projects_finished = parse_log(
      '/home/kaixuan/FDG_LLM/oss-fuzz-gen/run_spec_tmux_5samples.log')
  print(projects_finished)
