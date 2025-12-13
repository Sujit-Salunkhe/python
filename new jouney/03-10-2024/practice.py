# def find_first_position(cards,query,mid):
#     mid_number = cards[mid]
#     if mid_number == query:
#         if mid -1 >=0 and cards[mid - 1] == query:
#             return 'left'
        
#         return 'found'
    
#     if mid_number > query:
#         return 'right'
    
#     else:
#         return 'left'

# def locate_cards(cards,query):
#     lo = 0
#     hi = len(cards)-1
#     while lo <= hi:
#         mid = (lo + hi)//2
#         mid_number = cards[mid]
#         first_position = find_first_position(cards,query,mid)

#         if  first_position == 'found':
#                 return mid
#         elif first_position == 'right':
#             lo = mid + 1
#         else:   
#             hi = mid - 1
#     return -1


# query_answer = locate_cards([10,9,8,7,4,3,2,1],4)
# test_case = [8,8,6,6,6,5,4,3,2,1]
# query=6

# result = locate_cards(test_case,query)
# print(result)
# print(query_answer)


        
# test = [2,7,11,15]
# target = 9
# def twoSum (nums,target):
#     arr = []
#     for i in range(0,len(nums)): 
#         for j in range(i+1,len(nums) - 1):
#             print(i,nums[i],j+1,nums[j])
#             if nums[i] + nums[j] == target:
#                 return [i,j]

# def objMethod(nums,target):
#     res = {}
#     for i in range(len(nums)):
#         if (target - nums[i]) in res:
#             return [i,nums[target - nums[i]]]
#         else:
#             res[nums[i]] = i


# print(twoSum(test,target))


# class User:
#     def __init__(self,username,name,email):
#         self.username = username
#         self.name = name
#         self.email = email



class TreeNode:
    def __init__(self,key):
        self.key = key
        self.right = None
        self.left = None



node0 = TreeNode(3)
node1 = TreeNode(4)
node2 = TreeNode(5)



# node0.right = node1
# node0.left = node2

# print(node0.right.key)
# print(node0.left.key)
# print(node0.key)

tree_tuple = ((1,3,None),2,((None,3,4),5,(6,7,8)))


def parse_tuple(data):
    if isinstance(data,tuple) and len(data) == 3:
        node = TreeNode(data[1])
        node.left = parse_tuple(data[0])
        node.right = parse_tuple(data[2])
    
    elif data is None:
        node = None
    else:
        node = TreeNode(data)

    return node


tree = parse_tuple(tree_tuple)

# print(tree)
# print(tree.key)
# print(tree.left.key)
# print(tree.right.key)

# def tree_to_tuple(data):
#     if data is None:
#         return None;
#     data.left = tree_to_tuple(data.left)
#     data.right = tree_to_tuple(data.right)
#     return (data.left,data.key,data.right)


# # print(tree_to_tuple(tree))

# def Inorder_traversal(data):
#     if data is None:
#         return []
#     return (Inorder_traversal(data.left) + [data.key] + Inorder_traversal(data.right))
    
# print(Inorder_traversal(tree))


# def tree_height(data):
#     if data is None:
#         return 0 
#     return 1 +max(tree_height(data.left),tree_height(data.right))


# def max_size(data):
#     if data is None:
#         return 0
#     return 1 + max_size(data.left) + max_size(data.right)


# def is_bst(tree):
#     bstl,minl,maxl = is_bst(tree.left)
#     bstr,minr,maxr = is_bst(tree.right)

#     isbst = bstl and bstr (minr is None or minr > tree.key) and (maxl is None or maxr < tree.key)

#     min_key = min(remove_None([minl,tree.key,minr]))
#     max_key = max(remove_None([maxr,tree.key,maxl]))
#     return isbst,min_key,max_key 



class BstNode():
    def __init__(self,key,value=None):
        self.key = key
        self.value= value
        self.left = None
        self.right = None
        self.parent = None


def insertinbst(tree,key,value):
    if tree is None:
        tree =BstNode(key,value)
    elif key < tree.key:
        tree = insertinbst(tree.left,key,value)
        tree.left.parnet = tree
    elif key > tree.key:
        tree = insertinbst(tree.right,key,value)
        tree.right.parent = tree
    return node
    
 
def find (node,key):
    if node is None:
        return None
    elif node.key == key:
        return node
    elif node.key < key:
        return find(node.right,key)
    elif node.key > key:
        return find(node.left,key)
    return node

def update(node,key,value):
    target = find(node,key,value)
    if target is not None:
        target.value = value


def balance_bst(node):
    if node is None:
        return True,0
    balancel,heightl = balance_bst(node.left)
    balancer,heightr = balance_bst(node.right)
    balance = balancel and balancer and((heightl - heightr)<=1 )
    height = 1+max(heightl,heightr)
    return balance,height
    


def make_balced_bst(arr,lo=0,hi=None,parent=None):
    
    if hi is None:
        hi = len(arr) -1
    if lo > hi:
        return None
    mid = (lo + hi) //2
    key,value = arr[mid]
    root = BstNode(key,value)
    root.parent = parent
    root.left = make_balced_bst(arr,lo,root,hi= mid -1)
    root.right= make_balced_bst(arr,mid+1,hi,root)
    return root


def