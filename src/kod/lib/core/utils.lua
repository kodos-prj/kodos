-- Utility functions

function dumpTable(tbl, indent)
    indent = indent or 0
    for k, v in pairs(tbl) do
        print(string.rep(" ", indent) .. tostring(k) .. ":")
        if type(v) == "table" then
            dumpTable(v, indent + 2)
        else
            print(string.rep(" ", indent + 2) .. tostring(v))
        end
    end
end

function list(l)
    return setmetatable(l, {
        __tostring = function(t) 
            res = ''
            for k, v in pairs(t) do res = res .. '\''..v..'\' ' end
            return res
        end,
        __concat = function(x,y) 
            for _, v in ipairs(y) do table.insert(x, v) end return x end 
        })    
end

function map(m)
    return setmetatable(m, {
        __tostring = function(t) 
            res = ''
            for k, v in pairs(t) do res = res .. '(' .. k ..','.. tostring(v)..') ' end
            return res
        end,
        __concat = function(x,y) 
            for k, v in pairs(y) do rawset(x,k,v) end return x end 
        })    
end

function if_true(cond, m)
    if cond then
        return m
    end
    if type(m) == "table" then
        return {}
    end
    return nil
end

function if_else(cond, m_true, m_false)
    if cond then
        return m_true
    end
    return m_false
end

return {
    dumpTable = dumpTable,
    list = list,
    map = map,
    if_true = if_true,
    if_else = if_else,
}