import json
import sys
import os
sys.path.insert(0, os.path.abspath("."))
from core.schemas import Question

questions_data = [
    # =========================================================================
    # 1. INTRODUCTIONS & OPENINGS (Job / Placement, HR, Custom)
    # =========================================================================
    {
        "id": "q_intro_job_001",
        "question_text": "To start off, could you please introduce yourself and walk me through your professional background and key technical highlights?",
        "interview_type": ["job", "hr", "custom"],
        "level": "beginner",
        "topic": "professional_background",
        "difficulty": 0.2,
        "question_type": "introduction",
        "competencies": ["comm_clarity", "comm_relevance", "perf_confidence_delivery"],
        "follow_up_tags": ["career_path", "education", "core_skills"],
        "expected_answer_characteristics": ["concise_summary", "chronological_flow", "clear_articulation"],
        "technical_domain": None
    },
    {
        "id": "q_intro_job_002",
        "question_text": "Could you walk me through your journey in software engineering and highlight the project you are most proud of delivering?",
        "interview_type": ["job", "technical", "custom"],
        "level": "intermediate",
        "topic": "career_journey_and_achievements",
        "difficulty": 0.45,
        "question_type": "introduction",
        "competencies": ["comm_structure", "comm_explanation", "perf_engagement"],
        "follow_up_tags": ["project_ownership", "technical_impact", "stack_selection"],
        "expected_answer_characteristics": ["impact_metrics", "tech_stack_clarity", "ownership_signals"],
        "technical_domain": None
    },
    {
        "id": "q_intro_job_003",
        "question_text": "Could you briefly summarize your technical background and share what motivated you to apply for this engineering role today?",
        "interview_type": ["job", "hr"],
        "level": "intermediate",
        "topic": "motivation_and_background",
        "difficulty": 0.5,
        "question_type": "introduction",
        "competencies": ["comm_clarity", "int_professionalism", "comm_relevance"],
        "follow_up_tags": ["company_mission", "role_alignment", "value_add"],
        "expected_answer_characteristics": ["company_awareness", "role_interest", "skill_matching"],
        "technical_domain": None
    },
    {
        "id": "q_intro_job_004",
        "question_text": "As an experienced technologist, how would you summarize your core architectural strengths and your leadership or mentorship philosophy?",
        "interview_type": ["job", "technical"],
        "level": "advanced",
        "topic": "senior_profile_and_leadership",
        "difficulty": 0.8,
        "question_type": "introduction",
        "competencies": ["int_leadership", "comm_structure", "tech_technical_depth"],
        "follow_up_tags": ["system_ownership", "mentorship", "cross_functional_influence"],
        "expected_answer_characteristics": ["strategic_vision", "mentorship_examples", "architectural_maturity"],
        "technical_domain": None
    },

    # =========================================================================
    # 2. BEHAVIORAL & SITUATIONAL (STAR Method — Job / Placement & HR)
    # =========================================================================
    {
        "id": "q_behav_conflict_001",
        "question_text": "Tell me about a time you had a technical disagreement with a colleague or lead regarding system design. How did you resolve it?",
        "interview_type": ["job", "technical", "hr"],
        "level": "intermediate",
        "topic": "technical_conflict_resolution",
        "difficulty": 0.55,
        "question_type": "behavioral",
        "competencies": ["int_teamwork", "think_problem_solving", "comm_explanation"],
        "follow_up_tags": ["consensus_building", "data_driven_decisions", "compromise"],
        "expected_answer_characteristics": ["STAR_method", "respectful_dialogue", "objective_metrics_focus"],
        "technical_domain": None
    },
    {
        "id": "q_behav_deadline_001",
        "question_text": "Can you describe a situation where project scope expanded close to a hard release deadline? How did you prioritize and execute?",
        "interview_type": ["job", "hr", "custom"],
        "level": "intermediate",
        "topic": "deadline_and_scope_management",
        "difficulty": 0.5,
        "question_type": "behavioral",
        "competencies": ["think_decision_making", "int_adaptability", "comm_structure"],
        "follow_up_tags": ["triage", "stakeholder_communication", "tradeoffs"],
        "expected_answer_characteristics": ["STAR_method", "scope_triage", "calm_execution"],
        "technical_domain": None
    },
    {
        "id": "q_behav_failure_001",
        "question_text": "Can you share an experience where a deployment or feature did not go as planned? What was the root cause and what did you learn?",
        "interview_type": ["job", "technical", "hr"],
        "level": "intermediate",
        "topic": "post_mortem_and_learning",
        "difficulty": 0.6,
        "question_type": "behavioral",
        "competencies": ["think_critical_thinking", "int_professionalism", "int_adaptability"],
        "follow_up_tags": ["root_cause_analysis", "post_mortem", "preventative_measures"],
        "expected_answer_characteristics": ["humility", "blameless_retrospective", "systemic_fixes"],
        "technical_domain": None
    },
    {
        "id": "q_behav_ownership_001",
        "question_text": "Describe a project where you took full ownership from initial requirement gathering all the way to production monitoring.",
        "interview_type": ["job", "technical"],
        "level": "advanced",
        "topic": "end_to_end_ownership",
        "difficulty": 0.75,
        "question_type": "behavioral",
        "competencies": ["int_leadership", "tech_technical_depth", "comm_structure"],
        "follow_up_tags": ["architecture_decisions", "monitoring_alerts", "user_feedback"],
        "expected_answer_characteristics": ["comprehensive_lifecycle", "business_impact", "proactive_risk_management"],
        "technical_domain": None
    },
    {
        "id": "q_behav_stakeholder_001",
        "question_text": "Tell me about a time you had to explain a complex technical trade-off to a non-technical product manager or executive.",
        "interview_type": ["job", "hr"],
        "level": "beginner",
        "topic": "non_technical_communication",
        "difficulty": 0.35,
        "question_type": "behavioral",
        "competencies": ["comm_explanation", "comm_clarity", "comm_relevance"],
        "follow_up_tags": ["analogies", "business_impact", "active_listening"],
        "expected_answer_characteristics": ["plain_language", "business_context", "empathy"],
        "technical_domain": None
    },

    # =========================================================================
    # 3. PYTHON TECHNICAL QUESTIONS (Beginner, Intermediate, Advanced)
    # =========================================================================
    {
        "id": "q_py_beg_001",
        "question_text": "In Python, what is the core difference between mutable and immutable data types, and how does this affect function arguments passed by assignment?",
        "interview_type": ["technical", "job"],
        "level": "beginner",
        "topic": "python_mutability_and_references",
        "difficulty": 0.3,
        "question_type": "technical",
        "competencies": ["tech_technical_knowledge", "tech_technical_explanation", "comm_clarity"],
        "follow_up_tags": ["id_function", "default_arguments", "copy_vs_deepcopy"],
        "expected_answer_characteristics": ["lists_vs_tuples", "pass_by_object_reference", "mutation_side_effects"],
        "technical_domain": "Python"
    },
    {
        "id": "q_py_beg_002",
        "question_text": "How do lists, tuples, and sets differ in Python regarding ordering, mutability, and lookup time complexity?",
        "interview_type": ["technical", "job"],
        "level": "beginner",
        "topic": "python_built_in_collections",
        "difficulty": 0.35,
        "question_type": "technical",
        "competencies": ["tech_technical_knowledge", "tech_technical_accuracy"],
        "follow_up_tags": ["hash_table_lookup", "tuple_immutability", "set_uniqueness"],
        "expected_answer_characteristics": ["O(1)_set_lookup", "O(N)_list_lookup", "hashability_requirements"],
        "technical_domain": "Python"
    },
    {
        "id": "q_py_int_001",
        "question_text": "How do Python generators and the 'yield' statement optimize memory utilization when processing massive datasets compared to standard lists?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "generators_and_lazy_evaluation",
        "difficulty": 0.55,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "tech_technical_explanation", "think_problem_solving"],
        "follow_up_tags": ["iterator_protocol", "next_method", "memory_profiling"],
        "expected_answer_characteristics": ["lazy_evaluation", "generator_state_preservation", "O(1)_memory_footprint"],
        "technical_domain": "Python"
    },
    {
        "id": "q_py_int_002",
        "question_text": "Can you explain how decorators work in Python under the hood, and how you would write a decorator that accepts custom configuration arguments?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "decorators_and_closures",
        "difficulty": 0.6,
        "question_type": "technical",
        "competencies": ["tech_technical_knowledge", "tech_technical_explanation"],
        "follow_up_tags": ["functools_wraps", "closures", "first_class_functions"],
        "expected_answer_characteristics": ["closure_scope", "three_level_nested_functions", "metadata_preservation"],
        "technical_domain": "Python"
    },
    {
        "id": "q_py_int_003",
        "question_text": "How does Python's context management protocol operate with the 'with' statement, and when would you implement custom '__enter__' and '__exit__' methods?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "context_managers_and_resource_safety",
        "difficulty": 0.58,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "tech_technical_accuracy"],
        "follow_up_tags": ["exception_handling", "file_descriptors", "database_connections"],
        "expected_answer_characteristics": ["deterministic_cleanup", "exit_exception_suppression", "contextlib"],
        "technical_domain": "Python"
    },
    {
        "id": "q_py_adv_001",
        "question_text": "How does the Global Interpreter Lock (GIL) influence multi-threaded execution in CPython, and what concurrency models should you choose for CPU-bound versus I/O-bound tasks?",
        "interview_type": ["technical", "job"],
        "level": "advanced",
        "topic": "gil_and_concurrency_models",
        "difficulty": 0.85,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_problem_solving", "tech_technical_explanation"],
        "follow_up_tags": ["multiprocessing", "asyncio", "subinterpreters_pep684"],
        "expected_answer_characteristics": ["reference_counting_safety", "asyncio_for_io", "multiprocessing_for_cpu"],
        "technical_domain": "Python"
    },
    {
        "id": "q_py_adv_002",
        "question_text": "How would you identify, profile, and fix a memory leak or memory fragmentation issue in a high-throughput Python backend service?",
        "interview_type": ["technical", "job"],
        "level": "advanced",
        "topic": "python_memory_profiling_and_debugging",
        "difficulty": 0.88,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_problem_solving"],
        "follow_up_tags": ["tracemalloc", "objgraph", "garbage_collector_cycles"],
        "expected_answer_characteristics": ["circular_references", "c_extension_leaks", "profiling_tools"],
        "technical_domain": "Python"
    },

    # =========================================================================
    # 4. JAVA TECHNICAL QUESTIONS (Beginner, Intermediate, Advanced)
    # =========================================================================
    {
        "id": "q_java_beg_001",
        "question_text": "Could you explain the difference between the '==' operator and the '.equals()' method in Java, and why overriding 'equals()' requires overriding 'hashCode()'?",
        "interview_type": ["technical", "job"],
        "level": "beginner",
        "topic": "java_equality_and_hashcode_contract",
        "difficulty": 0.3,
        "question_type": "technical",
        "competencies": ["tech_technical_knowledge", "tech_technical_explanation"],
        "follow_up_tags": ["hashmap_buckets", "reference_comparison", "value_comparison"],
        "expected_answer_characteristics": ["reference_vs_value", "hashcode_contract", "hashmap_collision_hazard"],
        "technical_domain": "Java"
    },
    {
        "id": "q_java_beg_002",
        "question_text": "Why are Strings immutable in Java, and how does the String Constant Pool optimize memory allocation?",
        "interview_type": ["technical", "job"],
        "level": "beginner",
        "topic": "string_immutability_and_constant_pool",
        "difficulty": 0.35,
        "question_type": "technical",
        "competencies": ["tech_technical_knowledge", "comm_clarity"],
        "follow_up_tags": ["security", "thread_safety", "stringbuilder"],
        "expected_answer_characteristics": ["string_pool_interning", "thread_safety_benefits", "classloader_security"],
        "technical_domain": "Java"
    },
    {
        "id": "q_java_int_001",
        "question_text": "How does the Java Garbage Collector manage memory across Eden, Survivor, and Tenured spaces, and what triggers minor versus major GC cycles?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "jvm_generational_garbage_collection",
        "difficulty": 0.6,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "tech_technical_explanation"],
        "follow_up_tags": ["g1gc", "stop_the_world_pauses", "survivor_tenuring_threshold"],
        "expected_answer_characteristics": ["generational_hypothesis", "minor_vs_full_gc", "eden_survivor_promotion"],
        "technical_domain": "Java"
    },
    {
        "id": "q_java_int_002",
        "question_text": "How does 'ConcurrentHashMap' achieve thread safety in Java, and how does its internal locking mechanism differ from 'Hashtable' or synchronized maps?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "concurrency_and_concurrenthashmap",
        "difficulty": 0.65,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "tech_technical_accuracy"],
        "follow_up_tags": ["cas_operations", "lock_striping", "bucket_level_locks"],
        "expected_answer_characteristics": ["synchronized_bucket_nodes", "cas_for_empty_buckets", "high_concurrency_throughput"],
        "technical_domain": "Java"
    },
    {
        "id": "q_java_adv_001",
        "question_text": "How do Java 21 Virtual Threads (Project Loom) differ from platform OS threads, and how do they eliminate carrier thread blocking in high-scale I/O workloads?",
        "interview_type": ["technical", "job"],
        "level": "advanced",
        "topic": "virtual_threads_and_project_loom",
        "difficulty": 0.85,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_problem_solving"],
        "follow_up_tags": ["carrier_threads", "continuation_yield", "synchronized_pinning"],
        "expected_answer_characteristics": ["user_mode_scheduling", "stack_chunking_on_heap", "carrier_thread_unmounting"],
        "technical_domain": "Java"
    },
    {
        "id": "q_java_adv_002",
        "question_text": "How would you diagnose and resolve a thread deadlock or a CPU saturation spike in a multi-threaded enterprise Java application running on Linux?",
        "interview_type": ["technical", "job"],
        "level": "advanced",
        "topic": "jvm_troubleshooting_and_thread_dumps",
        "difficulty": 0.88,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_problem_solving"],
        "follow_up_tags": ["jstack", "top_dash_h", "async_profiler"],
        "expected_answer_characteristics": ["thread_dump_analysis", "nid_hex_correlation", "lock_ordering_fixes"],
        "technical_domain": "Java"
    },

    # =========================================================================
    # 5. DATA STRUCTURES & ALGORITHMS (DSA) (Beginner, Intermediate, Advanced)
    # =========================================================================
    {
        "id": "q_dsa_beg_001",
        "question_text": "What is the difference between an array and a linked list in terms of memory cache locality, insertion, and element retrieval complexity?",
        "interview_type": ["technical", "job"],
        "level": "beginner",
        "topic": "arrays_vs_linked_lists",
        "difficulty": 0.3,
        "question_type": "technical",
        "competencies": ["tech_technical_knowledge", "comm_explanation"],
        "follow_up_tags": ["cache_lines", "contiguous_memory", "pointer_overhead"],
        "expected_answer_characteristics": ["O(1)_random_access", "O(N)_traversal", "cpu_cache_locality"],
        "technical_domain": "DSA"
    },
    {
        "id": "q_dsa_beg_002",
        "question_text": "How would you implement a Queue using two Stacks, and what is the amortized time complexity for enqueue and dequeue operations?",
        "interview_type": ["technical", "job"],
        "level": "beginner",
        "topic": "stack_queue_implementations",
        "difficulty": 0.35,
        "question_type": "technical",
        "competencies": ["think_problem_solving", "tech_technical_accuracy"],
        "follow_up_tags": ["amortized_analysis", "fifo_vs_lifo"],
        "expected_answer_characteristics": ["in_stack_and_out_stack", "O(1)_amortized_dequeue", "transfer_only_when_empty"],
        "technical_domain": "DSA"
    },
    {
        "id": "q_dsa_int_001",
        "question_text": "How would you detect a cycle in a directed graph, and which algorithm or data structures would you select for optimal time and space complexity?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "graph_cycle_detection",
        "difficulty": 0.6,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_problem_solving"],
        "follow_up_tags": ["topological_sort", "kahns_algorithm", "dfs_back_edges"],
        "expected_answer_characteristics": ["three_color_dfs_or_kahns", "O(V+E)_time_complexity", "in_degree_tracking"],
        "technical_domain": "DSA"
    },
    {
        "id": "q_dsa_int_002",
        "question_text": "What are the core indicators that a problem should be solved with Dynamic Programming rather than a Greedy algorithm or brute-force recursion?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "dynamic_programming_paradigms",
        "difficulty": 0.62,
        "question_type": "technical",
        "competencies": ["think_reasoning", "tech_technical_explanation"],
        "follow_up_tags": ["overlapping_subproblems", "optimal_substructure", "memoization_vs_tabulation"],
        "expected_answer_characteristics": ["overlapping_subproblems", "optimal_substructure", "state_transition_clarity"],
        "technical_domain": "DSA"
    },
    {
        "id": "q_dsa_adv_001",
        "question_text": "How would you design and implement a Least Recently Used (LRU) Cache that supports both get() and put() in strict O(1) time complexity?",
        "interview_type": ["technical", "job"],
        "level": "advanced",
        "topic": "lru_cache_data_structure_design",
        "difficulty": 0.85,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_problem_solving"],
        "follow_up_tags": ["doubly_linked_list", "hash_map", "eviction_strategy"],
        "expected_answer_characteristics": ["hash_map_plus_doubly_linked_list", "dummy_head_and_tail", "O(1)_node_splicing"],
        "technical_domain": "DSA"
    },
    {
        "id": "q_dsa_adv_002",
        "question_text": "When would you choose a Segment Tree or Fenwick Tree (Binary Indexed Tree) over a prefix sum array for dynamic range queries and point updates?",
        "interview_type": ["technical", "job"],
        "level": "advanced",
        "topic": "advanced_range_query_trees",
        "difficulty": 0.88,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_critical_thinking"],
        "follow_up_tags": ["range_updates", "lazy_propagation", "log_n_complexity"],
        "expected_answer_characteristics": ["O(log_n)_updates", "O(log_n)_queries", "fenwick_bit_manipulation"],
        "technical_domain": "DSA"
    },

    # =========================================================================
    # 6. DATABASE MANAGEMENT SYSTEMS (DBMS) (Beginner, Intermediate, Advanced)
    # =========================================================================
    {
        "id": "q_dbms_beg_001",
        "question_text": "What is the operational difference between the WHERE clause and the HAVING clause in SQL, and when must HAVING be applied?",
        "interview_type": ["technical", "job"],
        "level": "beginner",
        "topic": "sql_filtering_and_aggregations",
        "difficulty": 0.3,
        "question_type": "technical",
        "competencies": ["tech_technical_knowledge", "comm_clarity"],
        "follow_up_tags": ["group_by", "aggregate_functions", "query_execution_order"],
        "expected_answer_characteristics": ["row_level_vs_group_level", "filtering_after_aggregation", "execution_order"],
        "technical_domain": "DBMS"
    },
    {
        "id": "q_dbms_beg_002",
        "question_text": "What is database normalization, and can you contrast First, Second, and Third Normal Forms (1NF, 2NF, 3NF)?",
        "interview_type": ["technical", "job"],
        "level": "beginner",
        "topic": "database_normalization_theory",
        "difficulty": 0.35,
        "question_type": "technical",
        "competencies": ["tech_technical_knowledge", "tech_technical_explanation"],
        "follow_up_tags": ["atomic_values", "partial_dependency", "transitive_dependency"],
        "expected_answer_characteristics": ["reducing_redundancy", "eliminating_update_anomalies", "functional_dependencies"],
        "technical_domain": "DBMS"
    },
    {
        "id": "q_dbms_int_001",
        "question_text": "How do B+ Tree indexes work internally in relational databases, and what distinguishes a clustered index from a non-clustered index?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "b_plus_tree_indexing_and_storage",
        "difficulty": 0.6,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "tech_technical_explanation"],
        "follow_up_tags": ["leaf_node_pointers", "physical_row_ordering", "covering_indexes"],
        "expected_answer_characteristics": ["physical_data_layout", "lookup_indirection", "range_scan_performance"],
        "technical_domain": "DBMS"
    },
    {
        "id": "q_dbms_int_002",
        "question_text": "Can you explain the four ACID properties and describe how database isolation levels protect against dirty reads, non-repeatable reads, and phantom reads?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "acid_and_transaction_isolation",
        "difficulty": 0.65,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "tech_technical_accuracy"],
        "follow_up_tags": ["mvcc", "read_committed", "serializable"],
        "expected_answer_characteristics": ["transaction_anomalies", "mvcc_snapshots", "pessimistic_vs_optimistic_locking"],
        "technical_domain": "DBMS"
    },
    {
        "id": "q_dbms_adv_001",
        "question_text": "How would you design a database sharding and replication topology for a high-scale application experiencing write bottlenecks on its primary database node?",
        "interview_type": ["technical", "job"],
        "level": "advanced",
        "topic": "sharding_replication_and_high_availability",
        "difficulty": 0.85,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_problem_solving"],
        "follow_up_tags": ["shard_key_selection", "cross_shard_joins", "replication_lag"],
        "expected_answer_characteristics": ["horizontal_partitioning", "consistent_hashing", "handling_replication_lag"],
        "technical_domain": "DBMS"
    },
    {
        "id": "q_dbms_adv_002",
        "question_text": "How do you evaluate an EXPLAIN query execution plan to diagnose and resolve an expensive sequential table scan on a table with tens of millions of records?",
        "interview_type": ["technical", "job"],
        "level": "advanced",
        "topic": "query_optimization_and_execution_plans",
        "difficulty": 0.88,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_problem_solving"],
        "follow_up_tags": ["index_condition_pushdown", "composite_indexes", "selectivity_cardinality"],
        "expected_answer_characteristics": ["cost_metrics", "composite_index_leftmost_prefix", "avoiding_implicit_type_conversions"],
        "technical_domain": "DBMS"
    },

    # =========================================================================
    # 7. WEB DEVELOPMENT (Beginner, Intermediate, Advanced)
    # =========================================================================
    {
        "id": "q_web_beg_001",
        "question_text": "What is the Document Object Model (DOM), and how does a modern browser parse and render HTML and CSS onto the screen?",
        "interview_type": ["technical", "job"],
        "level": "beginner",
        "topic": "dom_and_critical_rendering_path",
        "difficulty": 0.3,
        "question_type": "technical",
        "competencies": ["tech_technical_knowledge", "comm_explanation"],
        "follow_up_tags": ["dom_tree", "cssom", "reflow_and_repaint"],
        "expected_answer_characteristics": ["dom_plus_cssom_render_tree", "layout_phase", "paint_and_composite"],
        "technical_domain": "Web Development"
    },
    {
        "id": "q_web_beg_002",
        "question_text": "What is the difference between synchronous and asynchronous code in JavaScript, and what problem did Promises and async/await solve?",
        "interview_type": ["technical", "job"],
        "level": "beginner",
        "topic": "js_async_fundamentals",
        "difficulty": 0.35,
        "question_type": "technical",
        "competencies": ["tech_technical_knowledge", "comm_clarity"],
        "follow_up_tags": ["callback_hell", "event_loop", "promise_chaining"],
        "expected_answer_characteristics": ["non_blocking_io", "readability_improvements", "error_handling_try_catch"],
        "technical_domain": "Web Development"
    },
    {
        "id": "q_web_int_001",
        "question_text": "How does the JavaScript event loop handle microtasks versus macrotasks when processing Promises, MutationObservers, and setTimeout callbacks?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "event_loop_and_task_queues",
        "difficulty": 0.6,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "tech_technical_explanation"],
        "follow_up_tags": ["call_stack", "microtask_queue_draining", "render_pipeline"],
        "expected_answer_characteristics": ["call_stack_completion", "microtask_exhaustion_before_macrotask", "ui_render_timing"],
        "technical_domain": "Web Development"
    },
    {
        "id": "q_web_int_002",
        "question_text": "In modern React, how does the Virtual DOM reconciliation algorithm work, and when should you use useCallback and useMemo to prevent performance regressions?",
        "interview_type": ["technical", "job"],
        "level": "intermediate",
        "topic": "react_reconciliation_and_memoization",
        "difficulty": 0.62,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "tech_technical_accuracy"],
        "follow_up_tags": ["react_fiber", "referential_equality", "unnecessary_renders"],
        "expected_answer_characteristics": ["diffing_heuristics", "referential_stability", "avoiding_premature_optimization"],
        "technical_domain": "Web Development"
    },
    {
        "id": "q_web_adv_001",
        "question_text": "How would you identify and optimize Core Web Vitals—specifically Largest Contentful Paint (LCP) and Interaction to Next Paint (INP)—in a large-scale web application?",
        "interview_type": ["technical", "job"],
        "level": "advanced",
        "topic": "core_web_vitals_and_web_performance",
        "difficulty": 0.85,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_problem_solving"],
        "follow_up_tags": ["main_thread_long_tasks", "resource_fetch_priority", "code_splitting"],
        "expected_answer_characteristics": ["critical_image_preload", "reducing_main_thread_blocking", "server_side_rendering_tradeoffs"],
        "technical_domain": "Web Development"
    },
    {
        "id": "q_web_adv_002",
        "question_text": "How do you architect end-to-end security in a modern web application against Cross-Site Scripting (XSS), Cross-Site Request Forgery (CSRF), and CORS vulnerabilities?",
        "interview_type": ["technical", "job"],
        "level": "advanced",
        "topic": "web_security_and_browser_protections",
        "difficulty": 0.88,
        "question_type": "technical",
        "competencies": ["tech_technical_depth", "think_security"],
        "follow_up_tags": ["content_security_policy", "samesite_cookies", "preflight_options"],
        "expected_answer_characteristics": ["csp_headers", "http_only_and_samesite", "origin_validation_not_wildcards"],
        "technical_domain": "Web Development"
    },

    # =========================================================================
    # 8. HR & CULTURAL ALIGNMENT QUESTIONS (Beginner, Intermediate, Advanced)
    # =========================================================================
    {
        "id": "q_hr_beg_001",
        "question_text": "What motivated you to explore a career transition at this point, and what are you looking for in your next team environment?",
        "interview_type": ["hr", "job"],
        "level": "beginner",
        "topic": "career_motivation_and_goals",
        "difficulty": 0.25,
        "question_type": "behavioral",
        "competencies": ["comm_clarity", "int_professionalism"],
        "follow_up_tags": ["growth_opportunities", "culture_fit"],
        "expected_answer_characteristics": ["positive_framing", "growth_mindset", "clear_aspirations"],
        "technical_domain": None
    },
    {
        "id": "q_hr_int_001",
        "question_text": "Tell me about a time you received critical feedback from a peer or manager that was difficult to hear. How did you process and act on it?",
        "interview_type": ["hr", "job"],
        "level": "intermediate",
        "topic": "handling_feedback_and_growth",
        "difficulty": 0.5,
        "question_type": "behavioral",
        "competencies": ["int_adaptability", "int_professionalism", "comm_relevance"],
        "follow_up_tags": ["emotional_intelligence", "action_plan", "measurable_improvement"],
        "expected_answer_characteristics": ["emotional_maturity", "proactive_adjustment", "positive_outcome"],
        "technical_domain": None
    },
    {
        "id": "q_hr_int_002",
        "question_text": "How do you manage stress and maintain focus when juggling conflicting high-priority deliverables from different stakeholders?",
        "interview_type": ["hr", "job"],
        "level": "intermediate",
        "topic": "stress_and_priority_management",
        "difficulty": 0.52,
        "question_type": "behavioral",
        "competencies": ["think_decision_making", "int_adaptability", "perf_pace"],
        "follow_up_tags": ["timeboxing", "communication", "boundary_setting"],
        "expected_answer_characteristics": ["transparent_communication", "systematic_prioritization", "burnout_prevention"],
        "technical_domain": None
    },
    {
        "id": "q_hr_adv_001",
        "question_text": "Where do you envision your technical and leadership trajectory heading over the next three to five years, and how does this role fit that roadmap?",
        "interview_type": ["hr", "job"],
        "level": "advanced",
        "topic": "long_term_vision_and_alignment",
        "difficulty": 0.75,
        "question_type": "behavioral",
        "competencies": ["int_leadership", "comm_structure", "int_professionalism"],
        "follow_up_tags": ["tech_lead", "architect", "engineering_management"],
        "expected_answer_characteristics": ["realistic_ambition", "alignment_with_business", "commitment_to_learning"],
        "technical_domain": None
    },

    # =========================================================================
    # 9. ENGLISH COMMUNICATION QUESTIONS (Beginner, Intermediate, Advanced)
    # =========================================================================
    {
        "id": "q_eng_beg_001",
        "question_text": "Could you describe your favorite hobby or personal interest outside of work and explain what you enjoy most about it?",
        "interview_type": ["english"],
        "level": "beginner",
        "topic": "personal_interests_and_passions",
        "difficulty": 0.2,
        "question_type": "experience",
        "competencies": ["eng_fluency", "eng_pronunciation", "eng_vocabulary"],
        "follow_up_tags": ["relaxation", "skill_development"],
        "expected_answer_characteristics": ["continuous_speech", "descriptive_adjectives", "confident_tone"],
        "technical_domain": None
    },
    {
        "id": "q_eng_int_001",
        "question_text": "In your perspective, what are the primary advantages and drawbacks of remote work versus collaborating together in an in-person office?",
        "interview_type": ["english", "hr"],
        "level": "intermediate",
        "topic": "remote_work_perspectives",
        "difficulty": 0.5,
        "question_type": "opinion",
        "competencies": ["eng_sentence_structure", "eng_grammar", "comm_clarity"],
        "follow_up_tags": ["work_life_balance", "async_collaboration", "team_bonding"],
        "expected_answer_characteristics": ["balanced_arguments", "transitional_phrases", "clear_conclusion"],
        "technical_domain": None
    },
    {
        "id": "q_eng_adv_001",
        "question_text": "In your opinion, how will the rapid advancement of generative artificial intelligence reshape education and human creativity over the coming decade?",
        "interview_type": ["english", "custom"],
        "level": "advanced",
        "topic": "ai_impact_on_society_and_creativity",
        "difficulty": 0.8,
        "question_type": "opinion",
        "competencies": ["eng_vocabulary", "eng_sentence_structure", "think_reasoning"],
        "follow_up_tags": ["ethical_considerations", "critical_thinking", "economic_shifts"],
        "expected_answer_characteristics": ["nuanced_vocabulary", "complex_sentence_structures", "persuasive_flow"],
        "technical_domain": None
    }
]

# Validate every single question with Pydantic
validated = []
for q in questions_data:
    model = Question(**q)
    validated.append(model.model_dump())

print(f"Validated {len(validated)} questions successfully!")

with open("core/questions.json", "w", encoding="utf-8") as f:
    json.dump(validated, f, indent=2)

print("Overwrote core/questions.json successfully!")
