-- Utility functions for configuration processing
--
-- Provides metatable-based wrappers for list and map tables,
-- plus conditional evaluation helpers for configuration.

local M = {}

-- List wrapper: table with custom __tostring and concatenation
function M.list(l)
    return setmetatable(l, {
        __tostring = function(t) 
            local res = ''
            for k, v in pairs(t) do res = res .. '\''..v..'\' ' end
            return res
        end,
        __concat = function(x,y) 
            for _, v in ipairs(y) do table.insert(x, v) end return x end 
    })    
end

-- Map wrapper: table with custom __tostring and concatenation
function M.map(m)
    return setmetatable(m, {
        __tostring = function(t) 
            local res = ''
            for k, v in pairs(t) do res = res .. '(' .. k ..','.. tostring(v)..') ' end
            return res
        end,
        __concat = function(x,y) 
            for k, v in pairs(y) do rawset(x,k,v) end return x end 
    })    
end

-- Conditional: return table if condition true, empty table otherwise
function M.if_true(cond, m)
    if cond then
        return m
    end
    if type(m) == "table" then
        return {}
    end
    return nil
end

-- Conditional: return true value if condition, false value otherwise
function M.if_else(cond, m_true, m_false)
    if cond then
        return m_true
    end
    return m_false
end

return M
